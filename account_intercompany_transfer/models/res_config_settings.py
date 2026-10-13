from odoo import fields, models

from .res_company import BRIDGE_ACCOUNT_TYPES


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # A related field doesn't inherit the target's domain: repeat it, or the
    # picker would also offer archived accounts and accounts of any type.
    intercompany_transfer_account_id = fields.Many2one(
        related="company_id.intercompany_transfer_account_id",
        readonly=False,
        domain=[("account_type", "in", BRIDGE_ACCOUNT_TYPES)],
        check_company=True,
    )
