from odoo import fields, models


class AccountPaymentReviewWizardLine(models.TransientModel):
    _inherit = "account.payment.review.wizard.line"

    # A l10n_ar_payment_bundle main payment has an amount of 0: show the
    # payment order's total instead, the same figure the reviewer sees on it.
    payment_total = fields.Monetary(
        related="payment_id.payment_total",
        string="Payment total",
        currency_field="destination_currency_id",
    )
    destination_currency_id = fields.Many2one(related="payment_id.destination_currency_id", string="Debt currency")
