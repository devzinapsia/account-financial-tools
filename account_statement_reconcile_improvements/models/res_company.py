from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bank_statement_auto_reconcile_to_check = fields.Boolean(
        string="Flag auto-reconciled statement lines to check",
        default=True,
        help="When a bank statement line is reconciled automatically "
             "(by a reconciliation model, by the CUIT-based partner match "
             "on import, or by the auto-reconcile button), keep it flagged "
             "as \"to check\" instead of marking it fully reviewed.",
    )
