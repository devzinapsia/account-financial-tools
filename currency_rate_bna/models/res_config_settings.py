from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    currency_rate_service = fields.Selection(
        related='company_id.currency_rate_service',
        readonly=False
    )