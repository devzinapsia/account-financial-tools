from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAutoReconcileAndToCheckFlag(AccountTestInvoicingCommon):
    """3.7 (auto-reconcile unassigned button) and 3.9 (flag auto-reconciled
    lines to check) - the button only ever matches lines with no partner, so
    every line it reconciles must be flagged to check; a line reconciled some
    other way that already has a confirmed contact must not be.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _create_open_invoice(self, amount=100.0, date='2026-01-01'):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': date,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': amount,
                'quantity': 1,
                'tax_ids': [(6, 0, [])],
            })],
        })
        invoice.action_post()
        return invoice

    def _create_unreconciled_line(self, amount, date='2026-01-01', partner=False):
        statement = self.env['account.bank.statement'].create({
            'name': 'Test Statement',
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': date,
                'payment_ref': 'Unassigned line',
                'partner_id': partner.id if partner else False,
                'amount': amount,
                'journal_id': self.bank_journal.id,
            })],
        })
        return statement.line_ids

    def test_button_reconciles_a_unique_amount_and_date_match(self):
        invoice = self._create_open_invoice(amount=100.0, date='2026-01-01')
        line = self._create_unreconciled_line(amount=100.0, date='2026-01-01')

        reconciled_count = self.env['account.bank.statement.line'].action_auto_reconcile_unassigned_by_amount_and_date(line.ids)

        self.assertEqual(reconciled_count, 1)
        self.assertTrue(line.is_reconciled)
        self.assertTrue(invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable').reconciled)

    def test_button_skips_a_line_that_already_has_a_partner(self):
        self._create_open_invoice(amount=100.0, date='2026-01-01')
        line = self._create_unreconciled_line(amount=100.0, date='2026-01-01', partner=self.partner_a)

        reconciled_count = self.env['account.bank.statement.line'].action_auto_reconcile_unassigned_by_amount_and_date(line.ids)

        self.assertEqual(reconciled_count, 0)
        self.assertFalse(line.is_reconciled)

    def test_button_does_nothing_when_no_unique_candidate_exists(self):
        self._create_open_invoice(amount=100.0, date='2026-01-01')
        self._create_open_invoice(amount=100.0, date='2026-01-01')
        line = self._create_unreconciled_line(amount=100.0, date='2026-01-01')

        reconciled_count = self.env['account.bank.statement.line'].action_auto_reconcile_unassigned_by_amount_and_date(line.ids)

        self.assertEqual(reconciled_count, 0)
        self.assertFalse(line.is_reconciled)

    def test_line_reconciled_via_the_button_is_flagged_to_check(self):
        """Regression scope for 3.9: the button never has a confirmed
        contact backing its match (it only looks at lines with no partner),
        so every line it reconciles must always end up flagged to check
        when the company setting is on.
        """
        self._create_open_invoice(amount=100.0, date='2026-01-01')
        line = self._create_unreconciled_line(amount=100.0, date='2026-01-01')
        self.assertTrue(self.env.company.bank_statement_auto_reconcile_to_check, "Setting should default to on")

        self.env['account.bank.statement.line'].action_auto_reconcile_unassigned_by_amount_and_date(line.ids)

        self.assertFalse(line.move_id.checked, "A date+amount-only match with no partner must be flagged to check")

    def test_flag_to_check_skips_lines_with_a_confirmed_contact(self):
        """A line that already has a partner (e.g. resolved via CUIT on
        import) is reliable enough to count as reviewed - only the ones
        with no contact backing the match are worth a second look.
        """
        line = self._create_unreconciled_line(amount=100.0, partner=self.partner_a)
        line.move_id.checked = True

        line._flag_as_to_check_if_configured()

        self.assertTrue(line.move_id.checked, "A line with a confirmed contact must not be flagged to check")

    def test_flag_to_check_does_nothing_when_the_setting_is_off(self):
        self.env.company.bank_statement_auto_reconcile_to_check = False
        line = self._create_unreconciled_line(amount=100.0)
        line.move_id.checked = True

        line._flag_as_to_check_if_configured()

        self.assertTrue(line.move_id.checked, "Nothing should be flagged when the setting is disabled")
