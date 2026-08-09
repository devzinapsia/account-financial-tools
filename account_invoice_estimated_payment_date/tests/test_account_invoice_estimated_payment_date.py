from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountInvoiceEstimatedPaymentDate(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _make_move(self, move_type, invoice_date=None):
        vals = {
            "move_type": move_type,
            "partner_id": self.partner_a.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Test line",
                        "quantity": 1,
                        "price_unit": 100,
                    },
                )
            ],
        }
        if invoice_date:
            vals["invoice_date"] = invoice_date
        return self.env["account.move"].create(vals)

    def test_default_value_is_falsy(self):
        """A new vendor bill has no estimated payment date by default."""
        bill = self._make_move("in_invoice", invoice_date="2026-01-01")
        self.assertFalse(bill.estimated_payment_date)

    def test_set_estimated_payment_date_on_vendor_bill(self):
        """The estimated payment date can be written and read on a vendor bill."""
        bill = self._make_move("in_invoice", invoice_date="2026-01-01")
        bill.estimated_payment_date = "2026-02-15"
        self.assertEqual(str(bill.estimated_payment_date), "2026-02-15")

    def test_set_estimated_payment_date_on_customer_invoice(self):
        """The field is a regular account.move field: it can still be written
        on a customer invoice at the data level, even though the form view
        hides it for that move type (the visual restriction is not enforced
        as a business constraint)."""
        invoice = self._make_move("out_invoice")
        invoice.estimated_payment_date = "2026-02-15"
        self.assertEqual(str(invoice.estimated_payment_date), "2026-02-15")

    def test_set_estimated_payment_date_on_posted_vendor_bill(self):
        """The estimated payment date can still be written after the bill is
        posted, without resetting it to draft first."""
        bill = self._make_move("in_invoice", invoice_date="2026-01-01")
        bill.action_post()
        self.assertEqual(bill.state, "posted")

        bill.estimated_payment_date = "2026-02-15"
        self.assertEqual(str(bill.estimated_payment_date), "2026-02-15")
        self.assertEqual(bill.state, "posted")

    def test_search_by_estimated_payment_date(self):
        """account.move records can be searched by estimated_payment_date."""
        bill = self._make_move("in_invoice", invoice_date="2026-01-01")
        bill.estimated_payment_date = "2026-02-15"

        result = self.env["account.move"].search(
            [("estimated_payment_date", "=", "2026-02-15")]
        )
        self.assertIn(bill, result)

        result_none = self.env["account.move"].search(
            [("estimated_payment_date", "=", "2026-03-01")]
        )
        self.assertNotIn(bill, result_none)

    def test_group_by_estimated_payment_date(self):
        """account.move records can be grouped by estimated_payment_date."""
        bill_1 = self._make_move("in_invoice", invoice_date="2026-01-01")
        bill_1.estimated_payment_date = "2026-02-15"
        bill_2 = self._make_move("in_invoice", invoice_date="2026-01-02")
        bill_2.estimated_payment_date = "2026-02-15"
        bill_3 = self._make_move("in_invoice", invoice_date="2026-01-03")
        bill_3.estimated_payment_date = "2026-03-01"

        groups = self.env["account.move"]._read_group(
            [("id", "in", (bill_1 + bill_2 + bill_3).ids)],
            groupby=["estimated_payment_date:day"],
            aggregates=["id:recordset"],
        )
        groups_by_date = {date: moves for date, moves in groups}

        self.assertIn(bill_1.estimated_payment_date, groups_by_date)
        self.assertEqual(
            groups_by_date[bill_1.estimated_payment_date], bill_1 + bill_2
        )
        self.assertEqual(groups_by_date[bill_3.estimated_payment_date], bill_3)
