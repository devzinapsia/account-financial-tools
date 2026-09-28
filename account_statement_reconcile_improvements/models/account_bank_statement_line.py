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

        Called from the entry points where "no partner backing the match"
        can actually be true of the match itself: account.reconcile.model
        auto-triggered rules, and action_auto_reconcile_unassigned_by_amount_and_date()
        (the "Reconcile by date and amount" cog menu button, and the
        auto-reconcile-on-import option - both call the same method). The
        CUIT-based partner match on import never reconciles anything by
        itself (it only sets partner_id), and every *other* native
        auto-reconcile strategy account_accountant tries during import
        (exact amount, outstanding account entries, payment reference) is
        left at whatever account.move._compute_checked() already gives it -
        those aren't instrumented here at all, so they keep their native
        "reviewed by default" behavior.

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
        """ For the given statement lines that are still unreconciled, look
        for a unique open journal item (invoice/payment) matching on exact
        date and amount - and, when the line already has a confirmed
        contact (from the CUIT-in-free-text-legend match, or a column
        mapped directly to Contact), also matching that same partner - then
        reconcile against it using the same mechanism as the manual
        "Reconcile" dialog.

        Despite the method's name (kept for backward compatibility - it's
        the one the "Reconcile by date and amount" cog menu entry and the
        auto-reconcile-on-import option both call), this no longer requires
        the line to have no partner: a confirmed contact narrows the
        candidate search (only that partner's open items) instead of being
        a precondition. This complements account.reconcile.model, which
        cannot express a "match by amount and date only, no partner
        required" rule (see README "Decisiones de diseño").

        Returns the number of lines that were reconciled.
        """
        lines = self.browse(statement_line_ids).filtered(lambda line: not line.is_reconciled)
        reconciled_count = 0
        for line in lines:
            had_confirmed_partner = bool(line.partner_id)
            precision = line.currency_id.decimal_places
            domain = [
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
            ]
            if had_confirmed_partner:
                # Narrow to this same contact's own open items - a
                # confirmed partner is exact information, not just another
                # filter to loosen the amount/date match.
                domain.append(('partner_id', '=', line.partner_id.id))
            candidates = self.env['account.move.line'].search(domain)
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
                # force=True only when there was NO confirmed partner going
                # in: reconciling backfills partner_id from the matched
                # invoice/payment as a side effect, so line.partner_id would
                # already be set by now regardless - _flag_as_to_check_if_configured's
                # own "already has a partner" skip must be bypassed in that
                # case, or a match with no real contact backing it would
                # wrongly count as reviewed. When the partner WAS already
                # confirmed before this ran, force=False lets that natural
                # skip apply - it's reliable enough to count as reviewed.
                line._flag_as_to_check_if_configured(force=not had_confirmed_partner)
                reconciled_count += 1
        return reconciled_count
