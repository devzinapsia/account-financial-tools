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
        default=True,
        help="Odoo's own automatic bank reconciliation (triggered by having "
             "a contact on the line - set by the CUIT match on import, or "
             "manually) can match a statement line directly against an open "
             "invoice/bill's receivable/payable account, skipping the "
             "outstanding payment/receipt (\"cuenta puente\") account "
             "entirely when no such entry exists yet or doesn't match. For "
             "a bookkeeping flow where bank lines are only ever meant to "
             "settle through a receipt/payment order on an outstanding "
             "account, keep this enabled to stop automatic reconciliation "
             "from ever matching a statement line straight to a receivable/"
             "payable account - it still fully reconciles through "
             "outstanding accounts, and still falls back to reconcile "
             "models either way. Enabled by default, since most of our "
             "clients' bookkeeping works this way; disable it for a "
             "specific company that settles bank lines directly against "
             "invoices/bills instead.",
    )
    bank_statement_reconcile_dialog_default_journal = fields.Boolean(
        string="Pre-filter the journal in the reconciliation search dialog",
        default=True,
        help="The bank reconciliation screen's own \"Search: Journal Items "
             "to Match\" dialog searches every journal by design (useful to "
             "catch a payment registered against the wrong bank journal). "
             "For a company with many bank journals, that means seeing "
             "other banks' candidates mixed in every time. Enabled by "
             "default, this pre-selects the journal being reconciled as a "
             "search default - still a regular, removable filter, not a "
             "restriction. Disable it for a company with few enough "
             "journals that the extra candidates are never in the way.",
    )
