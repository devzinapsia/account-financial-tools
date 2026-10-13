import ast

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..models.account_intercompany_transfer import internal_write
from .common import IntercompanyTransferCommon


@tagged("post_install", "-at_install")
class TestCoexistenceAdhocInternalTransfer(IntercompanyTransferCommon):
    """Run with ingadhoc's account_internal_transfer installed: intercompany
    transfers and its internal transfers never show up in each other's
    process.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adhoc_installed = "is_internal_transfer" in cls.env["account.payment"]._fields

    def setUp(self):
        super().setUp()
        if not self.adhoc_installed:
            self.skipTest(
                "ingadhoc's account_internal_transfer is not installed: add it to the addons path and "
                "install it to run the separation tests."
            )

    def _adhoc_transfer(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "is_internal_transfer": True,
                "amount": 300.0,
                "journal_id": self.cash_a.id,
                "destination_journal_id": self.bank_a.id,
            }
        )
        payment.action_post()
        return payment | payment.paired_internal_transfer_payment_id

    def _adhoc_domain(self):
        action = self.env.ref("account_internal_transfer.action_account_payments_transfer")
        return ast.literal_eval(action.domain)

    def test_ours_not_in_adhoc_process(self):
        payments = self._transfer()
        payments = payments.origin_payment_id | payments.destination_payment_id
        Payment = self.env["account.payment"]
        self.assertFalse(Payment.search(self._adhoc_domain() + [("id", "in", payments.ids)]))
        self.assertFalse(Payment.search([("is_internal_transfer", "=", True), ("id", "in", payments.ids)]))
        for payment in payments:
            self.assertFalse(payment.is_internal_transfer)
            self.assertFalse(payment.destination_journal_id)
            self.assertFalse(payment.destination_company_id)
            self.assertFalse(payment.paired_internal_transfer_payment_id)
            # adhoc's overrides leave them alone: our counterpart, our partner.
            self.assertEqual(payment.destination_account_id, payment.company_id.intercompany_transfer_account_id)
            self.assertTrue(payment.partner_id)
            self.assertNotEqual(
                payment._get_name_receipt_report("account.report_payment_receipt_document"),
                "account_internal_transfer.report_account_transfer",
            )
            # Numbered by the journal's payment sequence, not by our ICT one.
            self.assertEqual(payment.name, payment.move_id.name)
            self.assertFalse(payment.name.startswith("ICT/"))

    def test_adhoc_not_in_our_process(self):
        adhoc_payments = self._adhoc_transfer()
        self.assertEqual(len(adhoc_payments), 2)
        Transfer = self.env["account.intercompany.transfer"]
        self.assertFalse(
            Transfer.search(
                [
                    "|",
                    ("origin_payment_id", "in", adhoc_payments.ids),
                    ("destination_payment_id", "in", adhoc_payments.ids),
                ]
            )
        )
        self.assertFalse(adhoc_payments.intercompany_transfer_id)
        # The wizard never offers payments, only journals and companies.
        wizard_fields = self.env["account.intercompany.transfer.wizard"]._fields.values()
        self.assertFalse([f for f in wizard_fields if f.type in ("many2one", "many2many") and f.comodel_name == "account.payment"])
        transfer = self._transfer()
        for payment in adhoc_payments:
            with internal_write(), self.assertRaisesRegex(ValidationError, "is an internal transfer"):
                payment.write({"intercompany_transfer_id": transfer.id})
            self.assertFalse(payment.name.startswith("ICT/"))


@tagged("post_install", "-at_install")
class TestCoexistencePaymentAuthorization(IntercompanyTransferCommon):
    """Run with account_payment_authorization installed: the outbound payment
    of a transfer is not a vendor payment, so no authorization policy
    intercepts it.
    """

    def setUp(self):
        super().setUp()
        if "authorization_state" not in self.env["account.payment"]._fields:
            self.skipTest("account_payment_authorization is not installed.")

    def test_outbound_payment_not_intercepted(self):
        self.env["account.payment.authorization.scheme"].create(
            {
                "name": "Every vendor payment",
                "domain": str([("amount", ">=", 0)]),
                "authorized_user_ids": [Command.set(self.env.ref("base.user_admin").ids)],
            }
        )
        transfer = self._transfer()
        origin = transfer.origin_payment_id
        self.assertEqual(origin.state, "in_process")
        self.assertEqual(origin.authorization_state, "not_required")
        self.assertFalse(origin.matched_scheme_ids)
