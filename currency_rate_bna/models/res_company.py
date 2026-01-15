from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    currency_rate_service = fields.Selection(
        selection_add=[('bna', 'BNA - Banco Nación Argentina (Zinapsia)')],
        ondelete={'bna': 'set default'}
    )