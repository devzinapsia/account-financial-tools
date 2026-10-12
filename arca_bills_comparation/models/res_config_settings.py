from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    arca_comparison_amount_tolerance = fields.Monetary(
        related="company_id.arca_comparison_amount_tolerance",
        readonly=False,
    )
    arca_comparison_percent_tolerance = fields.Float(
        related="company_id.arca_comparison_percent_tolerance",
        readonly=False,
    )
