from odoo import api, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def _flag_as_to_check_if_configured(self, force=False):
        """Mark these (already reconciled) lines as "to check" instead of
        leaving them fully reviewed, when the company setting is enabled -
        but only the ones with no confirmed contact. A line whose partner
        was already established (CUIT match on import, a reconcile.model
        rule that matched a specific partner) is reliable enough to count
        as reviewed; the ones reconciled purely by date+amount, with no
        partner backing the match, are the ones worth a second look.

        Shared by every automatic-reconciliation entry point this module
        touches: the CUIT-based partner match on import, the auto-reconcile
        button, and account.reconcile.model auto-triggered rules.

        :param force: skip the "no confirmed contact" check and flag
            unconditionally (subject to the company setting). Needed by the
            auto-reconcile button: reconciling a line backfills its
            partner_id from the matched invoice/payment as a side effect,
            so by the time this runs, line.partner_id would already be set
            even though the button only ever matches lines that had *no*
            partner going in - checking partner_id here would wrongly treat
            every one of its matches as "reviewed".
        """
        for line in self:
            if not force and line.partner_id:
                continue
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
            # amount_currency is False (not 0.0) on a statement line with no
            # foreign_currency_id set - the common case - so comparing it
            # directly against amount_residual_currency would never match a
            # real invoice/payment. Fall back to the plain company-currency
            # amount in that case.
            line_amount = line.amount_currency or line.amount
            candidates = candidates.filtered(
                lambda aml, line_amount=line_amount, precision=precision: (
                    round(abs(aml.amount_residual_currency), precision)
                    == round(abs(line_amount), precision)
                )
            )
            if len(candidates) != 1:
                continue
            line.set_line_bank_statement_line(candidates.ids)
            if line.is_reconciled:
                line._flag_as_to_check_if_configured(force=True)
                reconciled_count += 1
        return reconciled_count
