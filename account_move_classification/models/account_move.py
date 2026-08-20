from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    classification_id = fields.Many2one(
        "account.move.classification",
        string="Classification",
        copy=False,
        tracking=True,
    )
    classification_color = fields.Integer(
        related="classification_id.color",
        string="Classification Color",
        store=False,
    )
