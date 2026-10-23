from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestReconcileDialogDefaultJournal(AccountTestInvoicingCommon):
    """3.12: the company setting that controls whether the "Search: Journal
    Items to Match" dialog pre-filters by journal is exposed on
    account.bank.statement.line itself (a related field) so the bank
    reconciliation widget's own kanban view can fetch it for free alongside
    the rest of the statement line's data, with no extra RPC - see
    static/src/js/reconcile_dialog_default_journal.js, which reads it off
    the already-loaded record. This only tests that the related field wiring
    itself works; the actual JS behavior isn't something a Python test can
    cover.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _create_statement_line(self):
        statement = self.env['account.bank.statement'].with_context(skip_pdf_attachment_generation=True).create({
            'name': 'Test Statement',
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': '2026-01-01',
                'payment_ref': 'Test line',
                'amount': 100.0,
                'journal_id': self.bank_journal.id,
            })],
        })
        return statement.line_ids

    def test_related_field_reflects_the_company_setting(self):
        self.assertTrue(
            self.env.company.bank_statement_reconcile_dialog_default_journal,
            "Enabled by default",
        )
        line = self._create_statement_line()
        self.assertTrue(line.reconcile_dialog_default_journal)

        self.env.company.bank_statement_reconcile_dialog_default_journal = False
        line.invalidate_recordset(['reconcile_dialog_default_journal'])
        self.assertFalse(line.reconcile_dialog_default_journal)
