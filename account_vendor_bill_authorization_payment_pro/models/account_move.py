from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _check_vendor_bill_authorization_before_post(self):
        result = super()._check_vendor_bill_authorization_before_post()
        # account_payment_pro pays a bill with a "pay now" journal as soon
        # as it is confirmed: a bill that will require authorization can't
        # be paid before it is authorized, so it can't be confirmed with a
        # pay now journal either. Policies were just refreshed by super().
        to_pay_now = self.filtered(
            lambda m: m.state == "draft"
            and m.pay_now_journal_id
            and m.matched_policy_ids
            and m.authorization_state != "authorized"
        )
        if to_pay_now:
            raise UserError(
                _(
                    "The following vendor bills require authorization before "
                    "they can be paid, so they can't be paid on confirmation: "
                    "%s. Remove their pay now journal, confirm them and pay "
                    "them once they are authorized.",
                    ", ".join(to_pay_now.mapped("display_name")),
                )
            )
        return result
