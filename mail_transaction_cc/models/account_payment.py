from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _mail_transaction_cc_filter_records(self):
        """Internal transfers are never receipts nor payment orders: the paired
        payments of a transfer, and payments to the company's own partner (how
        the journal dashboard creates them)."""
        return super()._mail_transaction_cc_filter_records().filtered(
            lambda payment: not payment.paired_internal_transfer_payment_id
            and (not payment.partner_id or payment.partner_id != payment.company_id.partner_id)
        )
