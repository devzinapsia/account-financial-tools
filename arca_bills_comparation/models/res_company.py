from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    arca_comparison_amount_tolerance = fields.Monetary(
        string="ARCA comparison amount tolerance",
        currency_field="currency_id",
        default=0.02,
        help="Maximum difference, in the company currency, between ARCA's and Odoo's amounts "
        "still reported as a match in the ARCA vouchers comparison.",
    )
    arca_comparison_percent_tolerance = fields.Float(
        string="ARCA comparison percentage tolerance",
        digits=(16, 4),
        default=0.0,
        help="Maximum difference, as a percentage of ARCA's amount, still reported as a match in "
        "the ARCA vouchers comparison. Whichever of both tolerances is larger applies.",
    )
