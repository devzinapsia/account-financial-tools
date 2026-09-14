import base64

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDuplicateLineDetection(AccountTestInvoicingCommon):
    """3.4: importing a file that overlaps with an already-imported statement
    must not crash, and must report the skipped duplicate rows - regression
    test for a real bug found by hand-testing: the duplicate count was
    stashed on `self` inside _parse_import_data, but
    account_bank_statement_import_csv's execute_import() calls super() on
    self.with_context(...), a *different* recordset than the one
    execute_import() itself runs on, so reading it back crashed with
    AttributeError instead of just being silently wrong.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']
        # An existing line that the test import below will collide with:
        # same date, no partner, same amount.
        cls.env['account.bank.statement'].create({
            'name': 'Existing Statement',
            'journal_id': cls.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': '2026-01-05',
                'payment_ref': 'Already imported',
                'amount': 100.0,
                'journal_id': cls.bank_journal.id,
            })],
        })

    def _create_wizard(self, csv_content):
        return self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': csv_content.encode(),
            'file_name': 'test_import.csv',
            'file_type': 'text/csv',
        })

    def test_dryrun_import_with_a_duplicate_row_does_not_crash(self):
        csv_content = "Fecha,Importe\n2026-01-05,100.0\n2026-01-06,250.0\n"
        wizard = self._create_wizard(csv_content)
        options = {
            'has_headers': True,
            'bank_stmt_import': True,
            'quoting': '"',
            'separator': ',',
            'encoding': 'utf-8',
        }
        result = wizard.execute_import(
            fields=['date', 'amount'],
            columns=['Fecha', 'Importe'],
            options=options,
            dryrun=True,
        )
        messages = result.get('messages') or []
        self.assertFalse(
            any(m.get('type') == 'error' for m in messages),
            f"Unexpected error(s) in dryrun import result: {messages}",
        )
        warning_messages = [m['message'] for m in messages if m.get('type') == 'warning']
        self.assertTrue(
            any('1' in m and 'duplicate' in m.lower() for m in warning_messages),
            f"Expected a duplicate-row warning mentioning 1 skipped row, got: {warning_messages}",
        )
