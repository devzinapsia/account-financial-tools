from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bank_statement_auto_reconcile_to_check = fields.Boolean(
        related='company_id.bank_statement_auto_reconcile_to_check',
        readonly=False,
    )
    bank_statement_auto_reconcile_outstanding_only = fields.Boolean(
        related='company_id.bank_statement_auto_reconcile_outstanding_only',
        readonly=False,
    )
    bank_statement_reconcile_dialog_default_journal = fields.Boolean(
        related='company_id.bank_statement_reconcile_dialog_default_journal',
        readonly=False,
    )
