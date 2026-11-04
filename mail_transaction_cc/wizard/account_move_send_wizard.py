from odoo import api, fields, models


class AccountMoveSendWizard(models.TransientModel):
    _inherit = "account.move.send.wizard"

    transaction_cc_available = fields.Boolean(
        string="Email copies available", compute="_compute_transaction_cc_available",
    )
    transaction_cc = fields.Char(
        string="Cc",
        compute="_compute_transaction_cc",
        store=True,
        readonly=False,
        help="Visible copy, filled in by the email copy rules. It can be "
        "changed for this sending; several addresses are separated by commas. "
        "Type @ followed by the name or login of an internal user to add their email.",
    )
    transaction_bcc = fields.Char(
        string="Bcc",
        compute="_compute_transaction_cc",
        store=True,
        readonly=False,
        help="Hidden copy, filled in by the email copy rules: the recipients do "
        "not see these addresses. It can be changed for this sending. "
        "Type @ followed by the name or login of an internal user to add their email.",
    )

    @api.depends("move_id")
    def _compute_transaction_cc_available(self):
        Rule = self.env["mail.transaction.cc.rule"]
        for wizard in self:
            wizard.transaction_cc_available = bool(Rule._get_transaction_types(wizard.move_id))

    @api.depends("move_id", "mail_partner_ids")
    def _compute_transaction_cc(self):
        Rule = self.env["mail.transaction.cc.rule"]
        for wizard in self:
            wizard.transaction_cc, wizard.transaction_bcc = Rule._get_preview(
                wizard.move_id, document=True, partners=wizard.mail_partner_ids,
            )

    @api.onchange("transaction_cc", "transaction_bcc")
    def _onchange_transaction_cc_mentions(self):
        """Replace the "@name" mentions by the users' emails as soon as they
        are typed; the ones that cannot be resolved are reported."""
        if not self.transaction_cc_available:
            return
        Rule = self.env["mail.transaction.cc.rule"]
        company = Rule._get_record_company(self.move_id)
        all_errors = []
        for field_name in ("transaction_cc", "transaction_bcc"):
            text, errors = Rule._replace_user_mentions(self[field_name], company)
            all_errors += errors
            if text != (self[field_name] or ""):
                self[field_name] = text or False
        if all_errors:
            return {"warning": {"title": self.env._("Email copies"), "message": "\n".join(all_errors)}}

    def action_send_and_print(self, allow_fallback_pdf=False):
        self.ensure_one()
        if self.transaction_cc_available and self.sending_methods and "email" in self.sending_methods:
            Rule = self.env["mail.transaction.cc.rule"]
            cc, bcc = Rule._prepare_wizard_copies(self.move_id, self.transaction_cc, self.transaction_bcc)
            self = self.with_context(**Rule._get_override_context(self.move_id, cc, bcc))
        return super().action_send_and_print(allow_fallback_pdf=allow_fallback_pdf)
