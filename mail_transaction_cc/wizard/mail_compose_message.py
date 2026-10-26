from odoo import api, fields, models
from odoo.tools import email_normalize_all


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    transaction_cc_available = fields.Boolean(
        string="Email copies available", compute="_compute_transaction_cc_available",
    )
    transaction_cc = fields.Char(
        string="Cc",
        compute="_compute_transaction_cc",
        store=True,
        readonly=False,
        help="Visible copy, filled in by the email copy rules. It can be "
        "changed for this sending; several addresses are separated by commas.",
    )
    transaction_bcc = fields.Char(
        string="Bcc",
        compute="_compute_transaction_cc",
        store=True,
        readonly=False,
        help="Hidden copy, filled in by the email copy rules: the recipients do "
        "not see these addresses. It can be changed for this sending.",
    )

    def _get_transaction_cc_record(self):
        """The single transaction record this composer posts on, if any."""
        self.ensure_one()
        if self.composition_mode != "comment" or not self.model or self.model not in self.env:
            return None
        res_ids = self._evaluate_res_ids() if self.res_ids else []
        if len(res_ids) != 1:
            return None
        record = self.env[self.model].browse(res_ids)
        if not self.env["mail.transaction.cc.rule"]._get_transaction_types(record):
            return None
        return record

    @api.depends("composition_mode", "model", "res_ids")
    def _compute_transaction_cc_available(self):
        for composer in self:
            composer.transaction_cc_available = composer._get_transaction_cc_record() is not None

    @api.depends("composition_mode", "model", "res_ids", "template_id", "partner_ids")
    def _compute_transaction_cc(self):
        Rule = self.env["mail.transaction.cc.rule"]
        for composer in self:
            record = composer._get_transaction_cc_record()
            if record is None:
                composer.transaction_cc = composer.transaction_bcc = False
                continue
            composer.transaction_cc, composer.transaction_bcc = Rule._get_preview(
                record, document=bool(composer.template_id), partners=composer.partner_ids,
            )

    def _action_send_mail_comment(self, res_ids):
        """A composer using a template sends the document itself (e.g. receipt,
        quotation, RFQ / purchase order, reminders, receiptbook automatic
        email). The Cc / Bcc shown in the composer replace the rules."""
        context = {}
        if self.template_id:
            context["mail_transaction_cc_document"] = True
        record = self._get_transaction_cc_record()
        if record is not None:
            Rule = self.env["mail.transaction.cc.rule"]
            Rule._check_wizard_emails(self.transaction_cc, self.transaction_bcc)
            context.update(Rule._get_override_context(record, self.transaction_cc, self.transaction_bcc))
        if context:
            self = self.with_context(**context)
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
