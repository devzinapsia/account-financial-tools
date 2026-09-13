from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import RedirectWarning
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestBankStatementUnlink(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _create_reconciled_statement(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 100.0,
                'quantity': 1,
                'tax_ids': [(6, 0, [])],
            })],
        })
        invoice.action_post()

        statement = self.env['account.bank.statement'].create({
            'name': 'Test Statement',
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': invoice.invoice_date,
                'payment_ref': 'Payment for invoice',
                'partner_id': self.partner_a.id,
                'amount': invoice.amount_total,
                'journal_id': self.bank_journal.id,
            })],
        })
        st_line = statement.line_ids
        receivable_line = invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
        st_line.set_line_bank_statement_line(receivable_line.ids)
        return invoice, statement

    def test_unlink_without_confirmation_raises_redirect_warning(self):
        invoice, statement = self._create_reconciled_statement()
        self.assertTrue(statement.line_ids.is_reconciled)
        with self.assertRaises(RedirectWarning):
            statement.unlink()
        # Nothing should have been touched.
        self.assertTrue(statement.exists())
        self.assertTrue(invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable').reconciled)

    def test_unlink_confirmed_reopens_the_invoice_and_removes_the_lines(self):
        invoice, statement = self._create_reconciled_statement()
        statement_id = statement.id

        statement.with_context(statement_unlink_confirmed=True).unlink()

        self.assertFalse(self.env['account.bank.statement'].browse(statement_id).exists())
        self.assertFalse(
            invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable').reconciled,
            "The invoice's receivable line should be open again after the statement is deleted.",
        )
        self.assertIn(invoice.payment_state, ('not_paid', 'partial'))

    def test_unlink_a_statement_without_reconciled_lines_needs_no_confirmation(self):
        statement = self.env['account.bank.statement'].create({
            'name': 'Unreconciled Statement',
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': '2026-01-01',
                'payment_ref': 'Line 1',
                'amount': 100.0,
                'journal_id': self.bank_journal.id,
            })],
        })
        statement.unlink()
        self.assertFalse(statement.exists())
