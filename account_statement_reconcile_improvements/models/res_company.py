from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bank_statement_auto_reconcile_to_check = fields.Boolean(
        string="Flag auto-reconciled statement lines to check",
        default=True,
        help="When a bank statement line is reconciled automatically "
             "(by a reconciliation model, by the CUIT-based partner match "
             "on import, or by the auto-reconcile button) with no contact "
             "backing the match, keep it flagged as \"to check\" instead of "
             "marking it fully reviewed. Lines with a confirmed contact are "
             "always treated as reviewed.",
    )
    bank_statement_auto_reconcile_outstanding_only = fields.Boolean(
        string="Only auto-reconcile through outstanding accounts",
        default=False,
        help="Odoo's own automatic bank reconciliation (triggered by having "
             "a contact on the line - set by the CUIT match on import, or "
             "manually) can match a statement line directly against an open "
             "invoice/bill's receivable/payable account, skipping the "
             "outstanding payment/receipt (\"cuenta puente\") account "
             "entirely when no such entry exists yet or doesn't match. For "
             "a bookkeeping flow where bank lines are only ever meant to "
             "settle through a receipt/payment order on an outstanding "
             "account, enable this to stop automatic reconciliation from "
             "ever matching a statement line straight to a receivable/"
             "payable account - it still fully reconciles through "
             "outstanding accounts, and still falls back to reconcile "
             "models either way. Disabled by default to keep every "
             "existing installation's behavior unchanged.",
    )
