import logging

from odoo import models
from odoo.tools import email_normalize_all

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _mail_transaction_cc_filter_records(self):
        """Hook: return the records of ``self`` that can be a transaction for
        email copy rules. Override to exclude specific records (e.g. internal
        transfers on payments)."""
        return self

    # ------------------------------------------------------------
    # Outgoing notifications
    # ------------------------------------------------------------

    def _mail_transaction_cc_get_outgoing(self, message, recipients_data, msg_vals):
        """Return the resolved Cc / Bcc for an outgoing notification of
        ``message`` on this record, or an empty dict when no rule applies."""
        if len(self) != 1 or not self.id:
            return {}
        msg_vals = msg_vals or {}
        message_sudo = message.sudo()
        if (msg_vals.get("model") or message_sudo.model) != self._name:
            return {}
        if msg_vals.get("tracking_value_ids") or message_sudo.tracking_value_ids:
            return {}
        subtype_id = msg_vals["subtype_id"] if "subtype_id" in msg_vals else message_sudo.subtype_id.id
        subtype = self.env["mail.message.subtype"].sudo().browse(subtype_id)
        if not subtype or subtype.internal:
            return {}
        message_type = msg_vals.get("message_type") or message_sudo.message_type
        document = bool(self.env.context.get("mail_transaction_cc_document"))
        if not document and message_type != "comment":
            return {}
        # "To" = the external recipients, plus anyone chosen explicitly as a
        # recipient (internal users included); followers Odoo notifies on its
        # own are not "To"
        explicit_pids = set(
            msg_vals["partner_ids"] if "partner_ids" in msg_vals else message_sudo.partner_ids.ids
        )
        to_recipients = [
            data for data in recipients_data
            if data["notif"] == "email" and data["active"] and data["email_normalized"]
            and (data["share"] or data["id"] in explicit_pids)
        ]
        if not to_recipients:
            return {}
        resolved = self.env["mail.transaction.cc.rule"]._resolve_recipients(
            self,
            document=document,
            exclude_emails=[data["email_normalized"] for data in to_recipients],
        )
        if resolved:
            # external recipients first: they get the copies when several
            # "To" recipients are notified in separate emails
            ordered = sorted(
                (data for data in to_recipients if data["id"]), key=lambda data: not data["share"],
            )
            resolved["to_pids"] = [data["id"] for data in ordered]
            resolved["email_only"] = any(not data["id"] for data in to_recipients)
            resolved["done"] = False
        return resolved

    def _notify_thread_by_email(self, message, recipients_data, *, msg_vals=False, **kwargs):
        forward = self.env.context.get("mail_transaction_cc_forward")
        if forward:
            # incoming email forwarded to the rule addresses: internal users
            # receiving the forward do not get a second notification
            copied = forward["cc_normalized"] | forward["bcc_normalized"]
            recipients_data = [
                data for data in recipients_data
                if data["share"] or data["notif"] != "email" or data["email_normalized"] not in copied
            ]
            return super()._notify_thread_by_email(message, recipients_data, msg_vals=msg_vals, **kwargs)

        holder = self._mail_transaction_cc_get_outgoing(message, recipients_data, msg_vals)
        if not holder:
            return super()._notify_thread_by_email(message, recipients_data, msg_vals=msg_vals, **kwargs)
        # internal users already in Cc / Bcc receive that copy only, not a
        # separate notification email
        copied = holder["cc_normalized"] | holder["bcc_normalized"]
        recipients_data = [
            data for data in recipients_data
            if data["share"] or data["notif"] != "email" or data["email_normalized"] not in copied
        ]
        return super(
            MailThread, self.with_context(mail_transaction_cc_holder=holder)
        )._notify_thread_by_email(message, recipients_data, msg_vals=msg_vals, **kwargs)

    def _notify_by_email_get_final_mail_values(self, recipient_ids, mail_values, additional_values=None):
        values = super()._notify_by_email_get_final_mail_values(
            recipient_ids, mail_values, additional_values=additional_values
        )
        holder = self.env.context.get("mail_transaction_cc_holder")
        if not holder or holder["done"]:
            return values
        # only the email sent to a "To" recipient carries the copies, and only
        # once (one copy per address, even with several chunks or groups)
        main_pid = next((pid for pid in holder["to_pids"] if pid in recipient_ids), False)
        if main_pid or (not recipient_ids and holder["email_only"]):
            values.update({
                "email_cc": ",".join(holder["cc"]),
                "email_bcc": ",".join(holder["bcc"]),
                "transaction_cc": True,
                "transaction_cc_partner_id": main_pid,
            })
            holder["done"] = True
        return values

    # ------------------------------------------------------------
    # Incoming emails
    # ------------------------------------------------------------

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        forward = self._mail_transaction_cc_get_incoming(message, msg_vals)
        if not forward:
            return super()._notify_thread(message, msg_vals=msg_vals, **kwargs)
        res = super(
            MailThread, self.with_context(mail_transaction_cc_forward=forward)
        )._notify_thread(message, msg_vals=msg_vals, **kwargs)
        self._mail_transaction_cc_forward(message, forward)
        return res

    def _mail_transaction_cc_get_incoming(self, message, msg_vals):
        """Return the resolved Cc / Bcc to forward an incoming email received
        on this record ("all" scope rules only), or an empty dict."""
        if len(self) != 1 or not self.id:
            return {}
        msg_vals = msg_vals or {}
        message_sudo = message.sudo()
        if (msg_vals.get("message_type") or message_sudo.message_type) != "email":
            return {}
        if (msg_vals.get("model") or message_sudo.model) != self._name:
            return {}
        # addresses that already received the original email
        already = email_normalize_all("%s,%s" % (
            msg_vals.get("incoming_email_to", message_sudo.incoming_email_to) or "",
            msg_vals.get("incoming_email_cc", message_sudo.incoming_email_cc) or "",
        ))
        # never forward to the record's own reply-to (mail loop)
        already += email_normalize_all(self._mail_transaction_cc_reply_to(message_sudo))
        return self.env["mail.transaction.cc.rule"]._resolve_recipients(
            self, document=False, exclude_emails=already,
        )

    def _mail_transaction_cc_forward(self, message, forward):
        message_sudo = message.sudo()
        reply_to = self._mail_transaction_cc_reply_to(message_sudo)
        base_values = {
            "subject": message_sudo.subject or self.display_name,
            "body_html": message_sudo.body,
            "email_from": message_sudo.email_from,
            "reply_to": reply_to,
            "references": message_sudo.message_id or False,
            "attachment_ids": [(4, attachment.id) for attachment in message_sudo.attachment_ids],
            "auto_delete": True,
            "transaction_cc": True,
        }
        Mail = self.env["mail.mail"].sudo()
        if forward["cc"]:
            mails = Mail.create({
                **base_values,
                "email_to": ",".join(forward["cc"]),
                "email_bcc": ",".join(forward["bcc"]),
            })
        else:
            # Bcc only: one email per address so no address is exposed
            mails = Mail.create([
                {**base_values, "email_to": email} for email in forward["bcc"]
            ])
        _logger.info(
            "Incoming email %s on %s,%s forwarded to %d email copy address(es)",
            message.id, self._name, self.id,
            len(forward["cc"]) + len(forward["bcc"]),
        )
        mails.send_after_commit()
        return mails

    def _mail_transaction_cc_reply_to(self, message):
        """Reply-to of the record, so answers to a forwarded email come back to
        the record's chatter instead of going to the original sender."""
        return self._notify_get_reply_to(default=message.email_from).get(self.id) or ""
