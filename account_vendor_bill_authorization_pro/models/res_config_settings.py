from odoo import fields, models

from .res_company import PAY_NOW_JOURNAL_TYPES


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # A related field does not inherit the target field's domain: repeat it
    # here, scoped to the settings' company.
    bypass_journal_ids = fields.Many2many(
        related="company_id.bypass_journal_ids",
        readonly=False,
        domain="[('company_id', '=', company_id), ('type', 'in', %s)]" % (PAY_NOW_JOURNAL_TYPES,),
    )
    bypass_user_ids = fields.Many2many(
        related="company_id.bypass_user_ids",
        readonly=False,
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
    )
