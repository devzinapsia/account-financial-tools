from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    # Exposed on this model (not just on res.company) so the bank
    # reconciliation widget's own kanban view can fetch it for free
    # alongside the rest of the statement line's data - see
    # static/src/js/reconcile_dialog_default_journal.js, which reads it
    # straight from the already-loaded record instead of an extra RPC.
    reconcile_dialog_default_journal = fields.Boolean(
        related='company_id.bank_statement_reconcile_dialog_default_journal',
    )

    def _flag_as_to_check_if_configured(self, force=False):
        """Mark these (already reconciled) lines as "to check" instead of
        leaving them fully reviewed, when the company setting is enabled -
        but only the ones with no confirmed contact. A line whose partner
        was already established (CUIT match on import, a reconcile.model
        rule that matched a specific partner) is reliable enough to count
        as reviewed; the ones reconciled purely by date+amount, with no
        partner backing the match, are the ones worth a second look.

        Called from the two entry points where "no partner backing the
        match" is actually true of the match itself: account.reconcile.model
        auto-triggered rules, and the auto-reconcile button. The CUIT-based
        partner match on import never reconciles anything by itself (it only
        sets partner_id), and every *other* native auto-reconcile strategy
        account_accountant tries during import (exact amount, outstanding
        account entries, payment reference) is left at whatever
        account.move._compute_checked() already gives it - those aren't
        instrumented here at all, so they keep their native "reviewed by
        default" behavior.

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

    def _handle_reconciliation_matching_amount(self, st_move_ids, account_ids, remaining_st_line_ids, match_journal=False):
        # EXTENDS account_accountant
        if not match_journal:
            account_ids = self._exclude_receivable_payable_for_outstanding_only_companies(account_ids)
        return super()._handle_reconciliation_matching_amount(st_move_ids, account_ids, remaining_st_line_ids, match_journal=match_journal)

    def _match_accounts_query(self, st_move_ids, account_ids, remaining_st_line_ids, outstanding_account=False):
        # EXTENDS account_accountant
        if not outstanding_account:
            account_ids = self._exclude_receivable_payable_for_outstanding_only_companies(account_ids)
        return super()._match_accounts_query(st_move_ids, account_ids, remaining_st_line_ids, outstanding_account=outstanding_account)

    def _exclude_receivable_payable_for_outstanding_only_companies(self, account_ids):
        """3.13 - for companies with "Only auto-reconcile through outstanding
        accounts" enabled, drop their own receivable/payable accounts from
        the candidate set native auto-reconciliation is about to search
        (`_handle_reconciliation_matching_amount`/`_match_accounts_query`,
        called from account_accountant's `_try_auto_reconcile_statement_lines`
        - see models/res_company.py for the full rationale).

        Only called for the two call sites that search OUTSIDE outstanding
        accounts (`match_journal`/`outstanding_account` both False) - the
        outstanding-account pass itself (match_journal=True /
        outstanding_account=True) is never touched, since letting a line
        settle through a receipt/payment order is exactly the point.

        Safe for a multi-company batch without checking which company each
        line belongs to: the native SQL this feeds into already joins on
        `aml.company_id = st_line.company_id`, so dropping company A's own
        receivable/payable account ids from this shared list can only ever
        affect matching for company A's own lines. The `<=` (subset) check
        below, rather than a plain overlap, matters for v19's
        shared-chart-of-accounts support (`account.account.company_ids` is a
        Many2many): an account shared between a restricted and an
        unrestricted company must stay usable for the unrestricted one, so
        it's only excluded when every company it belongs to opted in.
        """
        restricted_companies = self.env['res.company'].sudo().search([
            ('bank_statement_auto_reconcile_outstanding_only', '=', True),
        ])
        if not restricted_companies:
            return account_ids
        excluded_ids = set(self.env['account.account'].browse(account_ids).filtered(
            lambda account: account.company_ids <= restricted_companies
            and account.account_type in ('asset_receivable', 'liability_payable')
        ).ids)
        if not excluded_ids:
            return account_ids
        return [account_id for account_id in account_ids if account_id not in excluded_ids]

    def action_create_vendor_bill(self):
        """3.11 - "Create bill" entry in the bank reconciliation screen's
        own "..." dropdown, right below "Upload Bills": for a purchase the
        user doesn't have any file for yet (no receipt/invoice on hand to
        scan), opens a blank vendor bill form to fill in by hand instead.

        account_accountant's own "Upload Bills" (create_document_from_attachment())
        always requires at least one attachment - it calls
        account.journal._create_document_from_attachment(attachment_ids),
        which has no variant that skips the attachment step. This mirrors
        that same method's own purchase-journal lookup, but creates a
        plain empty account.move instead, pre-filled with this line's
        contact and date so the user only has to add the actual invoice
        lines/amount.

        Deliberately does NOT try to reconcile the new bill against this
        statement line: unlike a file imported via OCR, a blank bill has
        no lines yet at all, so there's nothing to match against until the
        user fills it in and posts it - that happens through the normal
        reconcile flow afterwards, same as any other open invoice.
        """
        self.ensure_one()
        purchase_journal = self.env['account.journal'].search_fetch(
            domain=[*self.env['account.journal']._check_company_domain(self.company_id), ('type', '=', 'purchase')],
            field_names=['id'],
            limit=1,
        )
        invoice = self.env['account.move'].with_context(default_move_type='in_invoice').create({
            'move_type': 'in_invoice',
            'journal_id': purchase_journal.id,
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
        })
        return invoice._get_records_action()
