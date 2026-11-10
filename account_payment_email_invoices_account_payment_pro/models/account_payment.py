from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_email_invoice_payments(self):
        """account_payment_pro's _get_mached_payment() returns the payments
        whose reconciliations make up this one: the payment itself, plus the
        linked payments of a payment bundle (l10n_ar_payment_bundle), whose
        main payment has no journal entry of its own."""
        payments = super()._get_email_invoice_payments()
        return payments | self.browse(self._get_mached_payment())
