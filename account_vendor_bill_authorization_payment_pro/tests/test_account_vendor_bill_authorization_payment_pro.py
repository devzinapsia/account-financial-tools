from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountVendorBillAuthorizationPaymentPro(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.env.user.lang = "en_US"
        cls.company = cls.company_data["company"]
        cls.company.use_payment_pro = True
        cls.env.ref("base.group_user")._apply_group(
            cls.env.ref("account_payment_pro.group_pay_now_vendor_invoices")
        )
        # Without the vendor bill authorization "pay now" bypass of
        # account_vendor_bill_authorization_pro, if it happens to be
        # installed too.
        if "bypass_journal_ids" in cls.company._fields:
            cls.company.bypass_journal_ids = False

        cls.user_authorizer = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Authorizer",
                "login": "pp_authorizer",
                "lang": "en_US",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
            }
        )
        cls.bank_journal = cls.company_data["default_journal_bank"]
        for line in cls.bank_journal.outbound_payment_method_line_ids:
            if line.payment_method_id.code == "manual":
                line.payment_account_id = cls.bank_journal.default_account_id

        cls.classification = cls.env["account.move.classification"].create({"name": "Needs authorization"})
        cls.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Normal policy",
                "domain": str([("classification_id", "=", cls.classification.id)]),
                "authorized_user_ids": [Command.set(cls.user_authorizer.ids)],
            }
        )

    def _create_bill(self, classification=None, pay_now_journal=None, price=100.0):
        vals = {
            "move_type": "in_invoice",
            "journal_id": self.company_data["default_journal_purchase"].id,
            "partner_id": self.partner_a.id,
            "invoice_date": "2026-01-01",
            "invoice_line_ids": [
                Command.create({"name": "Test line", "quantity": 1, "price_unit": price, "tax_ids": False})
            ],
        }
        if classification:
            vals["classification_id"] = classification.id
        if pay_now_journal:
            vals["pay_now_journal_id"] = pay_now_journal.id
        return self.env["account.move"].create(vals)

    def _payable_line(self, bill):
        return bill.line_ids.filtered(lambda line: line.account_type == "liability_payable")

    def _new_vendor_payment(self):
        return self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "journal_id": self.bank_journal.id,
            }
        )

    def test_payment_receipt_leaves_out_bills_awaiting_authorization(self):
        payable = self._create_bill(price=50.0)
        payable.action_post()
        awaiting = self._create_bill(self.classification)
        awaiting.action_post()
        self.assertEqual(awaiting.authorization_state, "to_authorize")

        payment = self._new_vendor_payment()
        self.assertIn(self._payable_line(payable), payment.to_pay_move_line_ids)
        self.assertNotIn(self._payable_line(awaiting), payment.to_pay_move_line_ids)

        awaiting.with_user(self.user_authorizer).action_authorize_bill()
        payment.action_add_all()
        self.assertIn(self._payable_line(awaiting), payment.to_pay_move_line_ids)

    def test_bill_awaiting_authorization_cannot_be_added_by_hand(self):
        awaiting = self._create_bill(self.classification)
        awaiting.action_post()
        payment = self._new_vendor_payment()
        with self.assertRaises(ValidationError):
            payment.to_pay_move_line_ids = [Command.link(self._payable_line(awaiting).id)]

    def test_pay_button_blocked_with_payment_pro(self):
        awaiting = self._create_bill(self.classification)
        awaiting.action_post()
        with self.assertRaises(UserError):
            awaiting.action_register_payment()

    def test_pay_now_refused_when_authorization_is_required(self):
        bill = self._create_bill(self.classification, self.bank_journal)
        with self.assertRaises(UserError) as error:
            bill.action_post()
        self.assertIn("can't be paid on confirmation", str(error.exception))
        self.assertEqual(bill.state, "draft")
        self.assertFalse(bill.matched_payment_ids)

    def test_pay_now_still_works_when_no_authorization_is_required(self):
        bill = self._create_bill(pay_now_journal=self.bank_journal)
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.authorization_state, "not_required")
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
