from odoo import api, models
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_to_pay_move_lines_domain(self):
        # A payment receipt fills in all the debt of the partner: leave out
        # the vendor bills that can't be paid yet (pending authorization or
        # rejected), otherwise every payment to that vendor would be refused.
        return super()._get_to_pay_move_lines_domain() + [
            ("move_id.authorization_state", "not in", ["to_authorize", "rejected"])
        ]

    @api.constrains("to_pay_move_line_ids")
    def _check_to_pay_lines_vendor_bill_authorization(self):
        for payment in self.filtered(lambda p: p.state == "draft"):
            awaiting = payment.to_pay_move_line_ids.move_id.filtered(
                lambda m: m._is_awaiting_authorization()
            )
            if awaiting:
                raise ValidationError(awaiting._get_payment_blocked_error_message())
