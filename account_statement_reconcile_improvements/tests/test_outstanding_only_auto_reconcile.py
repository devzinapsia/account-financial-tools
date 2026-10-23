from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestOutstandingOnlyAutoReconcile(AccountTestInvoicingCommon):
    """3.13: with "Only auto-reconcile through outstanding accounts" enabled,
    Odoo's own automatic bank reconciliation (account_accountant's
    _try_auto_reconcile_statement_lines(), triggered here directly the same
    way the cron and the CUIT-match-on-import path do) must never match a
    statement line straight to an invoice/bill's receivable/payable account -
    only through an outstanding payment/receipt ("cuenta puente") account.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _create_unreconciled_line(self, partner, amount, date):
        statement = self.env['account.bank.statement'].with_context(skip_pdf_attachment_generation=True).create({
            'name': 'Test Statement',
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': date,
                'payment_ref': 'Unrelated bank label',
                'partner_id': partner.id,
                'amount': amount,
                'journal_id': self.bank_journal.id,
            })],
        })
        return statement.line_ids

    def test_native_auto_reconcile_matches_invoice_directly_when_disabled(self):
        self.env.company.bank_statement_auto_reconcile_outstanding_only = False
        invoice = self._create_invoice_one_line(partner_id=self.partner_a.id, price_unit=100.0, post=True)
        line = self._create_unreconciled_line(self.partner_a, 100.0, date=invoice.invoice_date)

        line._try_auto_reconcile_statement_lines()

        self.assertTrue(
            line.is_reconciled,
            "With the setting off, native auto-reconcile may still match straight to the invoice - "
            "this documents the pre-existing (and still available, opt-out) behavior",
        )

    def test_outstanding_only_setting_blocks_direct_invoice_match(self):
        self.env.company.bank_statement_auto_reconcile_outstanding_only = True
        invoice = self._create_invoice_one_line(partner_id=self.partner_a.id, price_unit=100.0, post=True)
        line = self._create_unreconciled_line(self.partner_a, 100.0, date=invoice.invoice_date)

        line._try_auto_reconcile_statement_lines()

        self.assertFalse(
            line.is_reconciled,
            "With the setting on, native auto-reconcile must not match straight to a receivable account",
        )

    def test_outstanding_only_setting_does_not_block_outstanding_account_match(self):
        """The setting must only ever exclude receivable/payable accounts -
        it must never interfere with a line settling normally through an
        outstanding payment/receipt account, which is the whole point of
        enabling it in the first place.
        """
        self.env.company.bank_statement_auto_reconcile_outstanding_only = True
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_a.id,
            'amount': 100.0,
            'journal_id': self.bank_journal.id,
            'date': '2026-01-01',
        })
        payment.action_post()
        line = self._create_unreconciled_line(self.partner_a, 100.0, date='2026-01-01')

        line._try_auto_reconcile_statement_lines()

        self.assertTrue(
            line.is_reconciled,
            "The setting must not block matching through the outstanding account a payment uses",
        )

    def test_other_company_without_the_setting_is_unaffected(self):
        """A multi-company batch (as the cron can produce) must only exclude
        receivable/payable accounts for companies that opted in - never for
        companies that didn't, even when processed in the very same call.
        """
        self.env.company.bank_statement_auto_reconcile_outstanding_only = True
        other_company_data = self.setup_other_company()
        other_company_data['company'].bank_statement_auto_reconcile_outstanding_only = False
        other_journal = other_company_data['default_journal_bank']
        other_partner = self.env['res.partner'].create({'name': 'Other Company Partner'})

        invoice = self._create_invoice_one_line(
            partner_id=other_partner.id, price_unit=100.0, post=True,
            company_id=other_company_data['company'].id,
            journal_id=other_company_data['default_journal_sale'].id,
        )
        statement = self.env['account.bank.statement'].with_company(
            other_company_data['company']
        ).with_context(skip_pdf_attachment_generation=True).create({
            'name': 'Other Company Statement',
            'journal_id': other_journal.id,
            'line_ids': [(0, 0, {
                'date': invoice.invoice_date,
                'payment_ref': 'Unrelated bank label',
                'partner_id': other_partner.id,
                'amount': 100.0,
                'journal_id': other_journal.id,
            })],
        })
        line = statement.line_ids

        line._try_auto_reconcile_statement_lines()

        self.assertTrue(
            line.is_reconciled,
            "A company that never enabled the setting must keep matching straight to its own invoices",
        )
