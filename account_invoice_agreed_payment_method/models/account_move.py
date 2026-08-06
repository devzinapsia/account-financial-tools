from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    agreed_payment_method_id = fields.Many2one(
        "account.move.agreed.payment.method",
        string="Agreed payment method",
    )
