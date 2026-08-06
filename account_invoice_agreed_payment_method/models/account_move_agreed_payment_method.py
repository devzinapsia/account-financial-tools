from odoo import fields, models


class AccountMoveAgreedPaymentMethod(models.Model):
    _name = "account.move.agreed.payment.method"
    _description = "Agreed Payment Method"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        "unique(name)",
        "The agreed payment method name must be unique.",
    )
