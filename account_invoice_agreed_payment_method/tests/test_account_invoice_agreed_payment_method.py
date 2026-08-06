from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

DEFAULT_METHOD_NAMES = {
    "Transferencia",
    "Mercado Pago",
    "Cheque",
    "Efectivo",
    "Tarjeta precargada",
    "Tarjeta de crédito",
    "Otro",
}


@tagged("post_install", "-at_install")
class TestAccountInvoiceAgreedPaymentMethod(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.method_model = cls.env["account.move.agreed.payment.method"]

    def _make_move(self, move_type):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
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

    def test_default_methods_exist(self):
        """The 7 default agreed payment methods are loaded on install."""
        names = set(self.method_model.search([]).mapped("name"))
        self.assertTrue(DEFAULT_METHOD_NAMES.issubset(names))

    def test_assign_agreed_payment_method_on_vendor_bill(self):
        """The agreed payment method can be assigned on a vendor bill."""
        method = self.method_model.search([("name", "=", "Efectivo")], limit=1)
        bill = self._make_move("in_invoice")
        bill.agreed_payment_method_id = method
        self.assertEqual(bill.agreed_payment_method_id, method)

    # The "readonly when not draft" behavior is enforced only in the form
    # view (readonly="state != 'draft'"), not as an ORM-level business
    # constraint, so it cannot be exercised directly with an ORM write in a
    # TransactionCase. It is a pure view restriction, same approach as
    # account_invoice_estimated_payment_date.

    def test_search_by_agreed_payment_method(self):
        """account.move records can be searched by agreed_payment_method_id."""
        method = self.method_model.search([("name", "=", "Cheque")], limit=1)
        bill = self._make_move("in_invoice")
        bill.agreed_payment_method_id = method

        result = self.env["account.move"].search(
            [("agreed_payment_method_id", "=", method.id)]
        )
        self.assertIn(bill, result)

        other_method = self.method_model.search([("name", "=", "Otro")], limit=1)
        result_none = self.env["account.move"].search(
            [("agreed_payment_method_id", "=", other_method.id)]
        )
        self.assertNotIn(bill, result_none)

    def test_group_by_agreed_payment_method(self):
        """account.move records can be grouped by agreed_payment_method_id."""
        method_a = self.method_model.search([("name", "=", "Transferencia")], limit=1)
        method_b = self.method_model.search([("name", "=", "Mercado Pago")], limit=1)

        bill_1 = self._make_move("in_invoice")
        bill_1.agreed_payment_method_id = method_a
        bill_2 = self._make_move("in_invoice")
        bill_2.agreed_payment_method_id = method_a
        bill_3 = self._make_move("in_invoice")
        bill_3.agreed_payment_method_id = method_b

        groups = self.env["account.move"]._read_group(
            [("id", "in", (bill_1 + bill_2 + bill_3).ids)],
            groupby=["agreed_payment_method_id"],
            aggregates=["id:recordset"],
        )
        groups_by_method = {method: moves for method, moves in groups}

        self.assertEqual(groups_by_method[method_a], bill_1 + bill_2)
        self.assertEqual(groups_by_method[method_b], bill_3)

    def test_unique_name(self):
        """Two agreed payment methods cannot share the same name."""
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.cr.savepoint():
                self.method_model.create({"name": "Efectivo"})
