from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestBankStatementDuplicateFile(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _create_statement(self, file_hash):
        return self.env['account.bank.statement'].create({
            'name': 'Test Statement',
            'journal_id': self.bank_journal.id,
            'import_file_hash': file_hash,
            'line_ids': [(0, 0, {
                'date': '2026-01-01',
                'payment_ref': 'Line 1',
                'amount': 100.0,
                'journal_id': self.bank_journal.id,
            })],
        })

    def test_reimporting_same_file_hash_for_same_journal_is_blocked(self):
        self._create_statement('a' * 64)
        with self.assertRaises(UserError):
            self._create_statement('a' * 64)

    def test_same_hash_on_a_different_journal_is_allowed(self):
        self._create_statement('b' * 64)
        other_journal = self.bank_journal.copy({'name': 'Other Bank', 'code': 'OBNK'})
        statement = self.env['account.bank.statement'].create({
            'name': 'Other Journal Statement',
            'journal_id': other_journal.id,
            'import_file_hash': 'b' * 64,
            'line_ids': [(0, 0, {
                'date': '2026-01-01',
                'payment_ref': 'Line 1',
                'amount': 100.0,
                'journal_id': other_journal.id,
            })],
        })
        self.assertTrue(statement)

    def test_statements_without_a_hash_are_never_considered_duplicates(self):
        statement1 = self.env['account.bank.statement'].create({
            'name': 'Manual Statement 1',
            'journal_id': self.bank_journal.id,
        })
        statement2 = self.env['account.bank.statement'].create({
            'name': 'Manual Statement 2',
            'journal_id': self.bank_journal.id,
        })
        self.assertTrue(statement1 and statement2)
