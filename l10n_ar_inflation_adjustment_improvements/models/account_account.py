from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    inflation_monetary_reviewed = fields.Boolean(
        string="Monetary classification reviewed",
        help="Check it once someone confirmed this non-monetary account is right as non-monetary: the inflation"
        " adjustment stops listing it among the accounts to review.",
    )
