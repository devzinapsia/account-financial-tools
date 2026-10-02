from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountVendorBillAuthorizationPro(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Chatter/error messages are rendered in the acting user's language;
        # pin it so the assertions on their text don't depend on which
        # languages happen to be loaded in the database.
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.env.user.lang = "en_US"
        cls.company = cls.company_data["company"]
        cls.company.use_payment_pro = True

        cls.pay_now_group = cls.env.ref("account_payment_pro.group_pay_now_vendor_invoices")
        cls.env.ref("base.group_user")._apply_group(cls.pay_now_group)

        users_model = cls.env["res.users"].with_context(no_reset_password=True)
        group_invoice = cls.env.ref("account.group_account_invoice")

        def create_user(login, name):
            return users_model.create(
                {
                    "name": name,
                    "login": login,
                    "email": f"{login}@test.example.com",
                    "lang": "en_US",
                    "company_id": cls.company.id,
                    "company_ids": [Command.set(cls.company.ids)],
                    "group_ids": [Command.set([group_invoice.id])],
                }
            )

        cls.user_bypass = create_user("bypass_user", "Bypass User")
        cls.user_other = create_user("bypass_other", "Not A Bypass User")
        cls.user_authorizer = create_user("bypass_authorizer", "Authorizer")

        cls.petty_cash_journal = cls.company_data["default_journal_cash"]
        cls.bank_journal = cls.company_data["default_journal_bank"]
        # Manual payments booked straight to the journal's account, so the
        # bill ends up fully paid right after confirmation.
        for journal in cls.petty_cash_journal | cls.bank_journal:
            for line in journal.outbound_payment_method_line_ids:
                if line.payment_method_id.code == "manual":
                    line.payment_account_id = journal.default_account_id

        cls.company.write(
            {
                "bypass_journal_ids": [Command.set(cls.petty_cash_journal.ids)],
                "bypass_user_ids": [Command.set(cls.user_bypass.ids)],
            }
        )

        classification_model = cls.env["account.move.classification"]
        cls.classification_normal = classification_model.create({"name": "Needs authorization"})
        cls.classification_blocked = classification_model.create({"name": "Always blocked"})

        policy_model = cls.env["account.vendor.bill.authorization.policy"]
        cls.policy_normal = policy_model.create(
            {
                "name": "Normal policy",
                "domain": str([("classification_id", "=", cls.classification_normal.id)]),
                "authorized_user_ids": [Command.set(cls.user_authorizer.ids)],
            }
        )
        cls.policy_always_block = policy_model.create(
            {
                "name": "Always block policy",
                "domain": str([("classification_id", "=", cls.classification_blocked.id)]),
                "always_block": True,
            }
        )

    # -- Helpers --------------------------------------------------------

    def _create_bill(self, classification=None, pay_now_journal=None, user=None):
        vals = {
            "move_type": "in_invoice",
            "journal_id": self.company_data["default_journal_purchase"].id,
            "partner_id": self.partner_a.id,
            "invoice_date": "2026-01-01",
            "invoice_line_ids": [
                Command.create({"name": "Test line", "quantity": 1, "price_unit": 100.0, "tax_ids": False})
            ],
        }
        if classification:
            vals["classification_id"] = classification.id
        if pay_now_journal:
            vals["pay_now_journal_id"] = pay_now_journal.id
        return self.env["account.move"].with_user(user or self.user_bypass).create(vals)

    def _post_expecting_error(self, bill, user):
        # Not self.assertRaises(): its savepoint rollback would also erase
        # the state left behind by the refused confirmation.
        try:
            bill.with_user(user).action_post()
            self.fail("Expected a UserError refusing to confirm the vendor bill.")
        except UserError as error:
            return error

    def _bypass_messages(self, bill):
        return bill.message_ids.filtered(lambda m: "bypasses vendor bill authorization" in (m.body or ""))

    # -- Scenarios ------------------------------------------------------

    def test_setting_off_never_bypasses(self):
        self.env.ref("base.group_user")._remove_group(self.pay_now_group)
        self.assertFalse(self.env["account.move"]._is_pay_now_vendor_enabled())
        bill = self._create_bill(self.classification_normal, self.petty_cash_journal)
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertEqual(bill.matched_policy_ids, self.policy_normal)
        self._post_expecting_error(bill, self.user_bypass)
        self.assertEqual(bill.state, "draft")
        self.assertFalse(self._bypass_messages(bill))

    def test_bypass_journal_skips_normal_policies(self):
        bill = self._create_bill(self.classification_normal, self.petty_cash_journal)
        self.assertFalse(bill.matched_policy_ids)
        self.assertEqual(bill.authorization_state, "not_required")
        bill.with_user(self.user_bypass).action_post()
        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.authorization_state, "not_required")
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertEqual(bill.matched_payment_ids.journal_id, self.petty_cash_journal)

    def test_always_block_wins_over_bypass(self):
        bill = self._create_bill(self.classification_blocked, self.petty_cash_journal)
        self.assertEqual(bill.matched_policy_ids, self.policy_always_block)
        self.assertTrue(bill.is_blocked)
        self._post_expecting_error(bill, self.user_bypass)
        self.assertEqual(bill.state, "draft")
        self.assertFalse(bill.matched_payment_ids)
        self.assertFalse(self._bypass_messages(bill))

    def test_without_pay_now_journal_normal_flow(self):
        bill = self._create_bill(self.classification_normal)
        self.assertEqual(bill.authorization_state, "to_authorize")
        self._post_expecting_error(bill, self.user_bypass)
        self.assertEqual(bill.state, "draft")

    def test_journal_not_in_bypass_list_refused(self):
        with self.assertRaises(UserError):
            self._create_bill(self.classification_normal, self.bank_journal)
        bill = self._create_bill(self.classification_normal)
        with self.assertRaises(UserError):
            bill.with_user(self.user_bypass).pay_now_journal_id = self.bank_journal

    def test_no_bypass_configuration_keeps_normal_flow(self):
        self.company.bypass_journal_ids = False
        bill = self._create_bill(self.classification_normal, self.bank_journal, user=self.user_other)
        self.assertTrue(bill.with_user(self.user_other).can_set_pay_now_journal)
        self.assertEqual(bill.authorization_state, "to_authorize")
        self._post_expecting_error(bill, self.user_other)
        self.assertEqual(bill.state, "draft")

    def test_user_not_allowed_cannot_use_bypass(self):
        bill = self._create_bill(self.classification_normal, user=self.user_other)
        self.assertFalse(bill.with_user(self.user_other).can_set_pay_now_journal)
        self.assertTrue(bill.with_user(self.user_bypass).can_set_pay_now_journal)
        with self.assertRaises(UserError):
            bill.with_user(self.user_other).pay_now_journal_id = self.petty_cash_journal

        # Set by an allowed user, then confirmed by a user who isn't.
        bill.with_user(self.user_bypass).pay_now_journal_id = self.petty_cash_journal
        self.assertEqual(bill.authorization_state, "not_required")
        error = self._post_expecting_error(bill, self.user_other)
        self.assertIn("not allowed to use the pay now journal", str(error))
        self.assertEqual(bill.state, "draft")

    def test_bypass_resets_earlier_authorization_decision(self):
        bill = self._create_bill(self.classification_normal)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        self.assertEqual(bill.authorization_state, "authorized")
        bill.with_user(self.user_bypass).pay_now_journal_id = self.petty_cash_journal
        self.assertEqual(bill.authorization_state, "not_required")

    def test_bypass_logs_chatter_message(self):
        bill = self._create_bill(self.classification_normal, self.petty_cash_journal)
        bill.with_user(self.user_bypass).action_post()
        messages = self._bypass_messages(bill)
        self.assertEqual(len(messages), 1)
        self.assertIn(self.petty_cash_journal.display_name, messages.body)

    def test_journal_security_hides_restricted_journal(self):
        # A journal totally restricted in account_journal_security can't
        # even be seen, let alone picked, by users left out of it -- even
        # users allowed to use the bypass.
        self.petty_cash_journal.user_ids = self.env.user | self.user_authorizer
        self.env.flush_all()
        visible = self.env["account.journal"].with_user(self.user_bypass).search(
            [("id", "=", self.petty_cash_journal.id)]
        )
        self.assertFalse(visible)

    # -- Payment authorization (account_payment_authorization) -----------

    def _create_payment_scheme(self, **vals):
        # Default domain: every vendor payment still pending confirmation,
        # i.e. a catch-all policy like "every payment must be authorized".
        return self.env["account.payment.authorization.scheme"].create(
            {"name": "All vendor payments", "authorized_user_ids": [Command.set(self.user_authorizer.ids)], **vals}
        )

    def test_bypass_payment_skips_payment_authorization(self):
        self._create_payment_scheme()
        bill = self._create_bill(self.classification_normal, self.petty_cash_journal)
        bill.with_user(self.user_bypass).action_post()
        self.assertEqual(bill.state, "posted")
        payment = bill.matched_payment_ids
        self.assertEqual(payment.journal_id, self.petty_cash_journal)
        self.assertNotEqual(payment.state, "draft")
        self.assertFalse(payment.matched_scheme_ids)
        self.assertEqual(payment.authorization_state, "not_required")
        self.assertIn(bill.payment_state, ("paid", "in_payment"))

    def test_payment_always_block_scheme_still_blocks_bypass_payment(self):
        self._create_payment_scheme(
            name="Block petty cash",
            domain=str([("journal_id", "=", self.petty_cash_journal.id)]),
            block_payment=True,
        )
        bill = self._create_bill(self.classification_normal, self.petty_cash_journal)
        self._post_expecting_error(bill, self.user_bypass)
        payment = self.env["account.payment"].search([("journal_id", "=", self.petty_cash_journal.id)])
        self.assertTrue(payment.matched_scheme_ids.block_payment)
        self.assertEqual(payment.state, "draft")

    def test_other_payments_still_require_payment_authorization(self):
        self._create_payment_scheme()
        payment_model = self.env["account.payment"].with_user(self.user_bypass)
        vals = {
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_a.id,
            "amount": 100.0,
        }
        # Same bypass journal, but not settling a bypassed vendor bill.
        petty_cash_payment = payment_model.create({**vals, "journal_id": self.petty_cash_journal.id})
        self.assertTrue(petty_cash_payment.matched_scheme_ids)
        # Settling a bill without pay now journal, from a non-bypass journal.
        bill = self._create_bill()
        bill.with_user(self.user_bypass).action_post()
        bank_payment = payment_model.create(
            {
                **vals,
                "journal_id": self.bank_journal.id,
                "to_pay_move_line_ids": [Command.set(bill.open_move_line_ids.ids)],
            }
        )
        self.assertTrue(bank_payment.matched_scheme_ids)
