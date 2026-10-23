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

    def test_second_batch_is_not_a_false_duplicate_of_the_first_batchs_own_rows(self):
        """A real bank file split into batches very often has two genuinely
        different, unrelated rows that happen to share the same date and
        amount (recurring fees, round transfer amounts) - common enough that
        a large real file produced hundreds of them in practice. By the time
        the second batch runs, the first batch's rows are already committed,
        so without excluding them, the probable-duplicate check in
        _filter_out_duplicate_lines() (no CUIT resolved here, so it falls
        back to date+amount only) wrongly flags every one of those
        coincidences - this is NOT the "reimporting an overlapping period"
        case the check is meant for, just an artifact of Odoo's own
        row-count batching splitting one coherent file into several
        execute_import() calls.
        """
        wizard = self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': (
                "Fecha,Importe,Descripcion\n"
                "2026-01-05,150.0,Comision mensual A\n"
                "2026-01-05,150.0,Comision mensual B\n"
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

        self.assertTrue(first_batch.get('ids'), "The first batch's own row must import")
        self.assertTrue(
            second_batch.get('ids'),
            "The second batch's row must import too, even though it coincidentally "
            "shares date+amount with the first batch's own row from the same file",
        )

    def test_a_genuinely_different_later_import_is_still_caught_as_a_duplicate(self):
        """The exclusion above must only apply to batches of the SAME
        ongoing import (import_batch_group_hash) - a later, separate import
        of a different file that genuinely overlaps an already-imported
        period must still be flagged, which is the actual feature this
        whole check exists for.
        """
        first_wizard = self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': "Fecha,Importe,Descripcion\n2026-01-05,150.0,Comision mensual\n".encode(),
            'file_name': 'original.csv',
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
        first_batch = first_wizard.execute_import(
            fields=fields, columns=columns, options={**base_options, 'skip': 0}, dryrun=False,
        )
        self.assertTrue(first_batch.get('ids'))

        second_wizard = self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            # A different file (different bytes/hash) with a row that
            # genuinely overlaps the one just imported above.
            'file': "Fecha,Importe,Descripcion\n2026-01-05,150.0,Comision mensual (reimport)\n".encode(),
            'file_name': 'reimport.csv',
            'file_type': 'text/csv',
        })
        second_batch = second_wizard.execute_import(
            fields=fields, columns=columns, options={**base_options, 'skip': 0}, dryrun=False,
        )

        self.assertFalse(
            second_batch.get('ids'),
            "A later, separate import of a different file overlapping an already-imported "
            "period must still be flagged as a probable duplicate and skipped",
        )
