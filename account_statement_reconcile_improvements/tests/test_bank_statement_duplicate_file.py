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

    def test_batched_import_of_a_large_file_does_not_block_its_own_later_batches(self):
        """base_import's own JS splits a file past its row-count limit into
        several execute_import() calls on the SAME wizard, one per row-range
        ('skip' growing each time) - every one of those calls hashes the
        exact same self.file (the whole original upload, not a per-batch
        slice). Only the first batch (skip 0) may claim the hash: letting
        every batch do it would collide with the statement the first batch
        already created, rejecting the rest of the very same import as a
        duplicate of itself.
        """
        wizard = self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': (
                "Fecha,Importe,Descripcion\n"
                "2026-01-01,100.0,Line 1\n"
                "2026-01-02,200.0,Line 2\n"
            ).encode(),
            'file_name': 'test_import.csv',
            'file_type': 'text/csv',
        })
        base_options = {
            'has_headers': True,
            'bank_stmt_import': True,
            'quoting': '"',
            'separator': ',',
            'encoding': 'utf-8',
        }
        fields = ['date', 'amount', 'payment_ref']
        columns = ['Fecha', 'Importe', 'Descripcion']

        first_batch = wizard.execute_import(
            fields=fields, columns=columns,
            options={**base_options, 'skip': 0, 'limit': 1},
            dryrun=False,
        )
        second_batch = wizard.execute_import(
            fields=fields, columns=columns,
            options={**base_options, 'skip': 1},
            dryrun=False,
        )

        first_line = self.env['account.bank.statement.line'].browse(first_batch['ids'])
        second_line = self.env['account.bank.statement.line'].browse(second_batch['ids'])
        self.assertTrue(first_line.statement_id.import_file_hash, "The first batch's statement must still carry the hash")
        self.assertFalse(second_line.statement_id.import_file_hash, "A later batch of the same import must not claim the hash too")
