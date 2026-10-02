from odoo import api, models

from odoo.addons.account_vendor_bill_authorization.models.account_move import VENDOR_BILL_TYPES


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.depends("journal_id", "to_pay_move_line_ids", "to_pay_move_line_ids.move_id.pay_now_journal_id")
    def _compute_matched_scheme_ids(self):
        super()._compute_matched_scheme_ids()
        if not self.env["account.move"]._is_pay_now_vendor_enabled():
            return
        for payment in self:
            if payment.matched_scheme_ids and payment._is_authorization_bypass_payment():
                # The payment that settles a vendor bill already paid with a
                # journal that bypasses authorization (the one
                # account_payment_pro creates when the bill is confirmed)
                # skips payment authorization too. "Always block" schemes
                # keep absolute priority, as they do for the bill.
                payment.matched_scheme_ids = payment.matched_scheme_ids.filtered("block_payment")

    def _is_authorization_bypass_payment(self):
        """True if this vendor payment comes from one of its company's
        journals that bypass authorization, and only settles vendor bills
        whose pay now journal is that same journal. Based on the payment's
        data only (no context key), so it can't be forced from outside, and
        independent of the current user, since it drives a stored computed
        field: who may use the bypass is enforced on the bill itself.
        """
        self.ensure_one()
        if self.payment_type != "outbound" or self.partner_type != "supplier":
            return False
        if self.journal_id not in self.company_id.sudo().bypass_journal_ids:
            return False
        bills = self.to_pay_move_line_ids.move_id
        return bool(bills) and all(
            bill.move_type in VENDOR_BILL_TYPES
            and bill.pay_now_journal_id == self.journal_id
            and bill._is_authorization_bypassed()
            for bill in bills
        )
