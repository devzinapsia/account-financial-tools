from odoo import api, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def _flag_as_to_check_if_configured(self):
        """Mark these (already reconciled) lines as "to check" instead of
        leaving them fully reviewed, when the company setting is enabled.

        Shared by every automatic-reconciliation entry point this module
        touches: the CUIT-based partner match on import, the auto-reconcile
        button, and account.reconcile.model auto-triggered rules.
        """
        for line in self:
            if line.company_id.bank_statement_auto_reconcile_to_check:
                line.move_id.checked = False

    @api.model
    def action_auto_reconcile_unassigned_by_amount_and_date(self, statement_line_ids):
        """ For the given statement lines that are still unreconciled and
        have no partner assigned, look for a unique open journal item
        (invoice/payment) matching on exact date and amount, and reconcile
        against it using the same mechanism as the manual "Reconcile" dialog.

        This complements account.reconcile.model, which cannot express a
        "match by amount and date only, no partner required" rule (see
        README "Decisiones de diseño").

        Returns the number of lines that were reconciled.
        """
        lines = self.browse(statement_line_ids).filtered(
            lambda line: not line.is_reconciled and not line.partner_id
        )
        reconciled_count = 0
        for line in lines:
            precision = line.currency_id.decimal_places
            candidates = self.env['account.move.line'].search([
                ('parent_state', 'in', ('draft', 'posted')),
                ('company_id', 'child_of', line.company_id.id),
                ('account_id.reconcile', '=', True),
                ('display_type', 'not in', ('line_section', 'line_note')),
                ('reconciled', '=', False),
                ('date', '=', line.date),
                ('statement_line_id', '!=', line.id),
                '|',
                ('account_id.account_type', 'not in', ('asset_receivable', 'liability_payable')),
                ('payment_id', '=', False),
            ])
            candidates = candidates.filtered(
                lambda aml, line=line, precision=precision: (
                    round(abs(aml.amount_residual_currency), precision)
                    == round(abs(line.amount_currency), precision)
                )
            )
            if len(candidates) != 1:
                continue
            line.set_line_bank_statement_line(candidates.ids)
            if line.is_reconciled:
                line._flag_as_to_check_if_configured()
                reconciled_count += 1
        return reconciled_count
