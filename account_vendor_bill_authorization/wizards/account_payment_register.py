from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _create_payments(self):
        # A payment registered on a journal without an outstanding account
        # is only linked to the bill, without any reconciliation, so the
        # reconciliation safety net would not catch it: check here too.
        self.line_ids.move_id._check_vendor_bill_authorization_before_payment()
        return super()._create_payments()
