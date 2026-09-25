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
        """3.7: button on this journal's dashboard card - for every
        unreconciled, no-partner statement line of this journal, look for a
        unique open invoice/payment matching on date and amount, and
        reconcile it. No selection needed: it always applies to every line
        currently pending, not just what happens to be loaded/visible.

        This lives here, as a plain object-type kanban button, instead of
        inside the bank reconciliation widget itself: that widget's own
        control panel only renders its action row when something is
        selected (a mechanism kanban mode doesn't even expose), so a button
        meant to run with no selection could never actually show up there.
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
