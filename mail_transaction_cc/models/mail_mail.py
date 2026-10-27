from odoo import api, fields, models
from odoo.tools import email_normalize_all
from odoo.tools.mail import email_split_and_format_normalize


class MailMail(models.Model):
    _inherit = "mail.mail"

    email_bcc = fields.Char("Bcc", help="Blind carbon copy message recipients")
    transaction_cc = fields.Boolean(
        string="Transaction copies",
        help="Technical: the Cc / Bcc of this email come from an email copy rule "
        "and travel in the same email received by the main recipient.",
    )

    transaction_cc_partner_id = fields.Many2one(
        "res.partner",
        string="Main recipient",
        help="Technical: the recipient whose email carries the Cc / Bcc of the "
        "email copy rules.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        mails = super().create(vals_list)
        # Notification emails: register the Cc addresses as email notifications
        # so they show in the message's delivery popover with their status.
        if self.env.context.get("mail_transaction_cc_holder"):
            notif_values = []
            for mail in mails.filtered(lambda m: m.transaction_cc and m.mail_message_id and m.email_cc):
                message = mail.mail_message_id
                notif_values += [{
                    "author_id": message.author_id.id,
                    "is_read": True,
                    "mail_email_address": email,
                    "mail_message_id": message.id,
                    "mail_mail_id": mail.id,
                    "notification_status": "ready",
                    "notification_type": "email",
                } for email in email_normalize_all(mail.email_cc)]
            if notif_values:
                self.env["mail.notification"].sudo().create(notif_values)
        return mails

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        """Put the Cc / Bcc of an email copy rule in the same email received by
        the main recipient. Standard Odoo sends ``email_cc`` as a separate email
        when the recipients are partners, and has no Bcc support at all."""
        results = super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
        if not self.transaction_cc or not results:
            return results
        # standalone Cc-only entry generated when there is no email_to
        cc_only = [
            entry for entry in results
            if not entry["partner_id"] and not entry["email_to"] and entry["email_cc"]
        ]
        targets = [entry for entry in results if entry not in cc_only] or results
        # main recipient: the one chosen when the email was created, else the
        # first external partner, else the first entry
        main = next(
            (entry for entry in targets
             if self.transaction_cc_partner_id and entry["partner_id"] == self.transaction_cc_partner_id),
            None,
        ) or next(
            (entry for entry in targets if entry["partner_id"] and entry["partner_id"].partner_share),
            targets[0],
        )
        if cc_only and main not in cc_only:
            results = targets
            for entry in results:
                entry["email_cc"] = []
            main["email_cc"] = email_split_and_format_normalize(self.email_cc)
            main["email_to_normalized"] = main["email_to_normalized"] + email_normalize_all(self.email_cc)
        bcc_list = email_split_and_format_normalize(self.email_bcc or "")
        if bcc_list:
            main["headers"] = dict(main["headers"], Bcc=", ".join(bcc_list))
            main["email_to_normalized"] = main["email_to_normalized"] + email_normalize_all(self.email_bcc)
        return results
