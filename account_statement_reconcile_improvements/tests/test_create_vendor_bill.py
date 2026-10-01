from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCreateVendorBill(AccountTestInvoicingCommon):
    """3.11: "Create Bill" entry in the bank reconciliation screen's "..."
    dropdown, for a purchase the user doesn't have any file for yet -
    unlike "Upload Bills" (account_accountant's own
    create_document_from_attachment), this never requires an attachment.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _create_unreconciled_line(self, amount=-100.0, date='2026-01-01', partner=False):
        statement = self.env['account.bank.statement'].create({
            'name': 'Test Statement',
            'journal_id': self.bank_journal.id,
            'line_ids': [(0, 0, {
                'date': date,
                'payment_ref': 'Unassigned expense',
                'partner_id': partner.id if partner else False,
                'amount': amount,
                'journal_id': self.bank_journal.id,
            })],
        })
        return statement.line_ids

    def test_creates_a_blank_bill_in_the_purchase_journal(self):
        line = self._create_unreconciled_line(partner=self.partner_a)

        action = line.action_create_vendor_bill()

        self.assertEqual(action.get('res_model'), 'account.move')
        invoice = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(invoice.move_type, 'in_invoice')
        self.assertEqual(invoice.journal_id.type, 'purchase')
        self.assertEqual(invoice.partner_id, self.partner_a)
        self.assertEqual(str(invoice.invoice_date), '2026-01-01')
        self.assertFalse(invoice.invoice_line_ids, "The bill must be blank - no lines guessed from the statement line")

    def test_works_even_with_no_partner_on_the_statement_line(self):
        line = self._create_unreconciled_line(partner=False)

        action = line.action_create_vendor_bill()

        invoice = self.env['account.move'].browse(action['res_id'])
        self.assertFalse(invoice.partner_id)
        self.assertEqual(invoice.move_type, 'in_invoice')

    def test_does_not_reconcile_the_new_blank_bill_against_the_line(self):
        """A blank bill has no lines at all yet, so there's nothing to
        match against - this is unlike the OCR-based "Upload Bills" flow,
        which can reconcile immediately when the scanned file already
        resolved a receivable/payable line.
        """
        line = self._create_unreconciled_line(partner=self.partner_a)

        line.action_create_vendor_bill()

        self.assertFalse(line.is_reconciled)
