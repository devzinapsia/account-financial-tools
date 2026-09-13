import os

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account_statement_reconcile_improvements.wizard.base_import_import import (
    _normalize_header_cell,
)
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestHeaderDetection(AccountTestInvoicingCommon):
    """3.9: banks like BBVA prepend metadata rows (account/period info,
    blank lines) before the real column-title row. The importer must find
    the real header on its own, with no manual file editing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']
        fixture_path = os.path.join(os.path.dirname(__file__), 'data', 'resumen_bbva_07_2026.xls')
        with open(fixture_path, 'rb') as fixture_file:
            cls.bbva_file = fixture_file.read()

    def _create_wizard(self):
        return self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': self.bbva_file,
            'file_name': 'resumen_bbva_07_2026.xls',
        })

    def test_bbva_leading_metadata_rows_are_skipped(self):
        wizard = self._create_wizard()
        _file_length, data_rows = wizard._read_file({'has_headers': True})
        header = [_normalize_header_cell(cell) for cell in data_rows[0]]
        self.assertTrue(any('fecha' in cell for cell in header))
        self.assertTrue(any('credito' in cell for cell in header))
        # The account/period metadata rows (rows 1-6 in the raw file) must
        # be gone, and so must any fully-blank separator row.
        self.assertTrue(all(any(cell not in (None, '') for cell in row) for row in data_rows))
        first_data_row = [_normalize_header_cell(cell) for cell in data_rows[1]]
        self.assertNotIn('empresa', first_data_row)

    def test_detection_is_a_no_op_when_the_header_is_already_row_0(self):
        wizard = self.env['base_import.import'].create({
            'res_model': 'account.bank.statement.line',
        })
        rows = [
            ['Fecha', 'Concepto', 'Importe'],
            ['2026-01-01', 'Test', '100.0'],
        ]
        self.assertEqual(wizard._detect_bank_statement_header_row(rows), 0)

    def test_detection_falls_back_to_zero_when_nothing_looks_like_a_header(self):
        wizard = self.env['base_import.import'].create({
            'res_model': 'account.bank.statement.line',
        })
        rows = [['x', 'y', 'z'], ['1', '2', '3']]
        self.assertEqual(wizard._detect_bank_statement_header_row(rows), 0)
