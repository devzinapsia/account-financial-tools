from odoo import models
from odoo.tools import email_normalize_all


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def _action_send_mail_comment(self, res_ids):
        """A composer using a template sends the document itself (e.g. receipt,
        RFQ / purchase order, purchase reminder, receiptbook automatic email)."""
        if self.template_id:
            self = self.with_context(mail_transaction_cc_document=True)
        return super()._action_send_mail_comment(res_ids)

    def _prepare_mail_values(self, res_ids):
        """Mass mail mode creates the emails directly, without notification:
        add the rule's Cc / Bcc to each record's email."""
        mail_values_all = super()._prepare_mail_values(res_ids)
        if self.composition_mode != "mass_mail" or not self.model or self.model not in self.env:
            return mail_values_all
        Rule = self.env["mail.transaction.cc.rule"]
        records = self.env[self.model].browse(list(mail_values_all))
        for record in records:
            values = mail_values_all[record.id]
            partner_ids = [
                command[1] if command[0] == 4 else None
                for command in values.get("recipient_ids") or []
                if isinstance(command, (list, tuple))
            ]
            partners = self.env["res.partner"].sudo().browse([pid for pid in partner_ids if pid])
            to_emails = email_normalize_all(values.get("email_to") or "")
            to_emails += [partner.email_normalized for partner in partners if partner.email_normalized]
            if not to_emails:
                continue
            resolved = Rule._resolve_recipients(
                record, document=bool(self.template_id), exclude_emails=to_emails,
            )
            if not resolved:
                continue
            existing_cc = values.get("email_cc")
            values.update({
                "email_cc": ",".join(filter(None, [existing_cc, *resolved["cc"]])),
                "email_bcc": ",".join(resolved["bcc"]),
                "transaction_cc": True,
            })
        return mail_values_all
