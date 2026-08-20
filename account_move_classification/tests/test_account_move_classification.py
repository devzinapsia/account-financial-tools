from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountMoveClassification(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.classification_a = cls.env["account.move.classification"].create(
            {"name": "Internal", "color": 1}
        )
        cls.classification_b = cls.env["account.move.classification"].create(
            {"name": "External", "color": 3}
        )

    def _make_out_invoice(self):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
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
        )

    def _make_in_invoice(self):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "quantity": 1,
                            "price_unit": 50,
                        },
                    )
                ],
            }
        )

    def test_assign_classification_to_out_invoice(self):
        """Classification can be assigned to a customer invoice."""
        invoice = self._make_out_invoice()
        invoice.classification_id = self.classification_a
        self.assertEqual(invoice.classification_id, self.classification_a)

    def test_assign_classification_to_in_invoice(self):
        """Classification can be assigned to a vendor bill."""
        bill = self._make_in_invoice()
        bill.classification_id = self.classification_b
        self.assertEqual(bill.classification_id, self.classification_b)

    def test_classification_not_required(self):
        """Classification field is optional — invoice saves fine without it."""
        invoice = self._make_out_invoice()
        self.assertFalse(invoice.classification_id)
        # Should not raise
        invoice.action_post()

    def test_unique_name_per_company(self):
        """Two classifications with the same name in the same company should fail."""
        with self.assertRaises(ValidationError):
            self.env["account.move.classification"].create(
                {"name": "Internal", "color": 5}
            )

    def test_unique_name_different_companies(self):
        """Same name is allowed if it belongs to different companies."""
        company2 = self.env["res.company"].create({"name": "Company B"})
        # Should not raise
        self.env["account.move.classification"].create(
            {"name": "Internal", "color": 2, "company_id": company2.id}
        )

    def test_search_by_classification_id(self):
        """account.move records can be searched by classification_id."""
        invoice = self._make_out_invoice()
        invoice.classification_id = self.classification_a

        result = self.env["account.move"].search(
            [("classification_id", "=", self.classification_a.id)]
        )
        self.assertIn(invoice, result)

        result_none = self.env["account.move"].search(
            [("classification_id", "=", self.classification_b.id)]
        )
        self.assertNotIn(invoice, result_none)
