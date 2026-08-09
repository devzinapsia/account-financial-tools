from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    estimated_payment_date = fields.Date(
        string="Estimated Payment Date",
        help="Date on which the vendor bill is expected to be paid, "
        "independent of the due date.",
        tracking=True,
    )
