from odoo import api, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # Dependencies add up along the MRO: only the new one is declared here.
    @api.depends("main_payment_id")
    def _compute_review_is_reviewable(self):
        return super()._compute_review_is_reviewable()

    def _review_reviewable_domain(self):
        # The payment order the user sees is the bundle's main payment; its
        # linked payments are just the payment methods (cash, check,
        # transfer...) it's made of, reviewed through it.
        return super()._review_reviewable_domain() + [("main_payment_id", "=", False)]
