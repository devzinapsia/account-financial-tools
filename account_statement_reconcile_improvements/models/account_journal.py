from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Snapshot of the last successful bank statement file import for this
    # journal: column mapping (by header name, so it survives column reordering)
    # plus the format options (encoding, separator, decimal/thousand separator,
    # sheet, ...) that base_import's own base_import.mapping doesn't cover,
    # since that model is keyed only by res_model (global across all journals/
    # banks), not per journal. See tools note in wizard/base_import_import.py.
    bank_statement_import_profile = fields.Json(
        string="Bank Statement Import Profile",
        copy=False,
        help="Technical field: last successful import settings (column "
             "mapping and file format options) for this journal, used to "
             "prefill the bank statement import wizard next time.",
    )

    def action_auto_reconcile_by_amount_and_date(self):
        """3.7: 'Reconcile by date and amount' entry in the bank
        reconciliation screen's own cog/Actions menu (see
        static/src/js/auto_reconcile_cog_menu.js) - for every unreconciled,
        no-partner statement line of this journal, look for a unique open
        invoice/payment matching on date and amount, and reconcile it. No
        selection needed: it always applies to every line currently
        pending, not just what happens to be loaded/visible.

        Not a plain <button> in that screen's own list/kanban view: Odoo
        only renders an always-visible control-panel button via <header>,
        which is gated on having a selection (a mechanism kanban mode
        doesn't even expose) - not usable for an action that intentionally
        never requires one. The cog menu is the one extension point that
        supports an unconditional entry there (the same one
        account_online_synchronization uses for its own "Find Duplicate/
        Missing Transactions" entries).

        Safe to trigger more than once in a row: a line this already
        reconciled picks up a partner_id as a side effect
        (set_line_bank_statement_line), so it drops out of the search
        below on the next call - nothing left to touch, no error.
        """
        self.ensure_one()
        lines = self.env['account.bank.statement.line'].search([
            ('journal_id', '=', self.id),
            ('is_reconciled', '=', False),
            ('partner_id', '=', False),
        ])
        reconciled_count = lines.action_auto_reconcile_unassigned_by_amount_and_date(lines.ids)
        message = self.env._(
            "Line(s) reconciled automatically: %(count)s", count=reconciled_count,
        ) if reconciled_count else self.env._(
            "No matching open item found for any unassigned, unreconciled line."
        )
        self.env.user._bus_send('simple_notification', {
            'type': 'success' if reconciled_count else 'info',
            'sticky': False,
            'title': self.env._("Auto-reconcile by date and amount"),
            'message': message,
        })
        return reconciled_count
