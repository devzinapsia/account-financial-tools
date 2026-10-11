from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentReview(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Chatter messages and errors are rendered in the acting user's
        # language; pin it so assertions don't depend on loaded languages.
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.env.user.lang = "en_US"
        cls.company = cls.company_data["company"]
        cls.company.write(
            {
                "payment_review_enabled": True,
                "payment_review_min_amount": 0.0,
                "payment_review_exempt_domain": "[]",
                "payment_review_answer_days": 3,
            }
        )

        group_invoice = cls.env.ref("account.group_account_invoice")
        group_reviewer = cls.env.ref("account_payment_review.group_payment_reviewer")
        users = cls.env["res.users"].with_context(no_reset_password=True)

        def create_user(login, groups):
            return users.create(
                {
                    "name": login.replace("_", " ").title(),
                    "login": login,
                    "lang": "en_US",
                    "email": f"{login}@test.example.com",
                    "company_id": cls.company.id,
                    "company_ids": [Command.set(cls.company.ids)],
                    "group_ids": [Command.set(groups.ids)],
                }
            )

        cls.issuer = create_user("review_issuer", group_invoice)
        cls.accountant = create_user("review_accountant", group_invoice)
        cls.reviewer = create_user("review_reviewer", group_reviewer)
        cls.reviewer_issuer = create_user("review_reviewer_issuer", group_invoice | group_reviewer)
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.cash_journal = cls.company_data["default_journal_cash"]
        cls.subtype = cls.env.ref("account_payment_review.mt_payment_review")
        cls.observation_type = cls.env.ref("account_payment_review.mail_activity_payment_review_observation")
        cls.answer_type = cls.env.ref("account_payment_review.mail_activity_payment_review_answer")

    def _create_payment(self, amount=100.0, user=None, journal=None, post=True, **vals):
        values = {
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_a.id,
            "amount": amount,
            "journal_id": (journal or self.bank_journal).id,
        }
        values.update(vals)
        payment = self.env["account.payment"].with_user(user or self.issuer).create(values)
        if post:
            payment.action_post()
        return payment.with_user(self.env.user)

    def _review(self, payments, result, comment=False, user=None):
        return payments.with_user(user or self.reviewer)._review_set_result(result, comment)

    def _review_messages(self, payment):
        return payment.message_ids.filtered(lambda m: m.subtype_id == self.subtype)

    # ------------------------------------------------------------------
    # Initial status on confirmation
    # ------------------------------------------------------------------

    def test_confirm_sets_pending_and_issuer(self):
        payment = self._create_payment(post=False)
        self.assertFalse(payment.review_state, "A draft payment is outside the review circuit.")
        payment.with_user(self.accountant).action_post()
        self.assertIn(payment.state, ("in_process", "paid"))
        self.assertEqual(payment.review_state, "pending")
        self.assertTrue(payment.review_is_reviewable)
        self.assertEqual(payment.review_issuer_id, self.accountant, "The issuer is whoever confirmed the payment.")
        self.assertIn(payment, self.env["account.payment"].search([("review_is_reviewable", "=", True)]))

    def test_customer_payment_not_reviewable(self):
        payment = self._create_payment(payment_type="inbound", partner_type="customer")
        self.assertFalse(payment.review_state)
        self.assertFalse(payment.review_is_reviewable)
        self.assertNotIn(payment, self.env["account.payment"].search([("review_is_reviewable", "=", True)]))
        with self.assertRaises(UserError):
            self._review(payment, "reviewed")

    def test_min_amount_exemption(self):
        self.company.payment_review_min_amount = 1000.0
        small = self._create_payment(amount=500.0)
        big = self._create_payment(amount=1500.0)
        self.assertEqual(small.review_state, "not_required")
        self.assertEqual(big.review_state, "pending")

    def test_domain_exemption(self):
        self.company.payment_review_exempt_domain = str([("journal_id", "=", self.cash_journal.id)])
        cash = self._create_payment(journal=self.cash_journal)
        bank = self._create_payment()
        self.assertEqual(cash.review_state, "not_required")
        self.assertEqual(bank.review_state, "pending")

    def test_circuit_disabled(self):
        self.company.payment_review_enabled = False
        payment = self._create_payment()
        self.assertFalse(payment.review_state)
        # Still reviewable on purpose.
        self._review(payment, "reviewed")
        self.assertEqual(payment.review_state, "reviewed")

    def test_reconfirm_keeps_decision(self):
        payment = self._create_payment()
        self._review(payment, "reviewed")
        payment.action_draft()
        payment.action_post()
        self.assertEqual(payment.review_state, "reviewed")

    # ------------------------------------------------------------------
    # Reviewing
    # ------------------------------------------------------------------

    def test_review_ok(self):
        payment = self._create_payment()
        self._review(payment, "reviewed", "All good")
        self.assertEqual(payment.review_state, "reviewed")
        self.assertEqual(payment.review_user_id, self.reviewer)
        self.assertTrue(payment.review_date)
        self.assertEqual(payment.review_comment, "All good")
        message = self._review_messages(payment)
        self.assertEqual(len(message), 1)
        self.assertEqual(message.author_id, self.reviewer.partner_id, "The message is the reviewer's signature.")
        self.assertIn("OK", message.body)
        self.assertIn("All good", message.body)
        self.assertTrue(message.subtype_id.internal)
        self.assertFalse(payment.activity_ids)

    def test_observation_requires_comment(self):
        payment = self._create_payment()
        with self.assertRaises(UserError):
            self._review(payment, "observed", "   ")
        self.assertEqual(payment.review_state, "pending")

    def test_observation_creates_activity_for_issuer(self):
        payment = self._create_payment()
        self._review(payment, "observed", "Wrong journal")
        self.assertEqual(payment.review_state, "observed")
        activity = payment.activity_ids
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.activity_type_id, self.observation_type)
        self.assertEqual(activity.user_id, self.issuer)
        self.assertIn("Wrong journal", activity.note)
        self.assertEqual(activity.date_deadline, fields.Date.context_today(payment) + timedelta(days=3))
        self.assertIn("with observations", self._review_messages(payment).body)

    def test_answer_and_review_again(self):
        payment = self._create_payment()
        self._review(payment, "observed", "Missing receipt")
        payment.with_user(self.issuer)._review_answer("Receipt attached")
        self.assertEqual(payment.review_state, "answered")
        self.assertEqual(payment.review_answer, "Receipt attached")
        activity = payment.activity_ids
        self.assertEqual(activity.activity_type_id, self.answer_type, "The issuer's activity is replaced.")
        self.assertEqual(activity.user_id, self.reviewer)
        self.assertEqual(len(self._review_messages(payment)), 2)

        self._review(payment, "reviewed")
        self.assertEqual(payment.review_state, "reviewed")
        self.assertFalse(payment.activity_ids)
        self.assertFalse(payment.review_answer)

    def test_reviewer_can_change_their_mind(self):
        payment = self._create_payment()
        self._review(payment, "reviewed")
        self._review(payment, "observed", "Found something at month end")
        self.assertEqual(payment.review_state, "observed")
        self._review(payment, "not_required")
        self.assertEqual(payment.review_state, "not_required")
        self.assertFalse(payment.activity_ids)

    # ------------------------------------------------------------------
    # Wizards
    # ------------------------------------------------------------------

    def _open_review_wizard(self, payments):
        return (
            self.env["account.payment.review.wizard"]
            .with_user(self.reviewer)
            .with_context(active_model="account.payment", active_ids=payments.ids)
            .create({})
        )

    def test_single_review_wizard(self):
        payment = self._create_payment()
        wizard = self._open_review_wizard(payment)
        self.assertTrue(wizard.is_single)
        wizard.write({"result": "observed", "comment": "Check the amount"})
        wizard.action_confirm()
        self.assertEqual(payment.review_state, "observed")
        self.assertEqual(payment.review_comment, "Check the amount")

    def test_mass_review_wizard(self):
        payments = self._create_payment() | self._create_payment(amount=200.0) | self._create_payment(amount=300.0)
        wizard = self._open_review_wizard(payments)
        self.assertFalse(wizard.is_single)
        self.assertEqual(wizard.line_ids.payment_id, payments)
        lines = {line.payment_id: line for line in wizard.line_ids}
        lines[payments[1]].result = "observed"
        with self.assertRaises(UserError):
            wizard.action_confirm()
        lines[payments[1]].comment = "Duplicated?"
        lines[payments[2]].result = "not_required"
        wizard.action_confirm()
        self.assertEqual(payments.mapped("review_state"), ["reviewed", "observed", "not_required"])
        self.assertEqual(payments[1].activity_ids.user_id, self.issuer)

    def test_review_wizard_rejects_non_reviewable(self):
        draft = self._create_payment(post=False)
        with self.assertRaises(UserError):
            self._open_review_wizard(draft)

    def test_answer_wizard(self):
        payment = self._create_payment()
        self._review(payment, "observed", "Why cash?")
        wizard = (
            self.env["account.payment.review.answer.wizard"]
            .with_user(self.issuer)
            .with_context(active_model="account.payment", active_id=payment.id)
            .create({"answer": "Vendor has no bank account"})
        )
        self.assertEqual(wizard.payment_id, payment)
        wizard.action_confirm()
        self.assertEqual(payment.review_state, "answered")

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    def test_only_reviewers_can_review(self):
        payment = self._create_payment()
        with self.assertRaises(AccessError):
            self._review(payment, "reviewed", user=self.accountant)
        with self.assertRaises(AccessError):
            self._open_review_wizard(payment).with_user(self.accountant).action_confirm()
        self.assertEqual(payment.review_state, "pending")

    def test_review_fields_cannot_be_written_directly(self):
        payment = self._create_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.issuer).write({"review_state": "reviewed"})
        with self.assertRaises(AccessError):
            payment.with_user(self.issuer).write({"review_user_id": self.issuer.id})
        with self.assertRaises(AccessError):
            self.env["account.payment"].with_user(self.issuer).create(
                {
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                    "partner_id": self.partner_a.id,
                    "amount": 10.0,
                    "journal_id": self.bank_journal.id,
                    "review_state": "reviewed",
                }
            )

    def test_reviewer_cannot_review_own_payment(self):
        own = self._create_payment(user=self.reviewer_issuer)
        with self.assertRaises(UserError):
            self._review(own, "reviewed", user=self.reviewer_issuer)
        # Someone else's payment is fine for them.
        other = self._create_payment()
        self._review(other, "reviewed", user=self.reviewer_issuer)
        self.assertEqual(other.review_state, "reviewed")

    def test_reviewers_from_settings(self):
        group = self.env.ref("account_payment_review.group_payment_reviewer")
        settings = self.env["res.config.settings"].create({})
        self.assertIn(self.reviewer, settings.payment_reviewer_ids)
        self.assertNotIn(self.accountant, settings.payment_reviewer_ids)

        settings = self.env["res.config.settings"].create(
            {"payment_reviewer_ids": [Command.set((settings.payment_reviewer_ids | self.accountant).ids)]}
        )
        settings.execute()
        self.assertIn(self.accountant, group.user_ids)
        payment = self._create_payment()
        self._review(payment, "reviewed", user=self.accountant)
        self.assertEqual(payment.review_state, "reviewed")

        settings = self.env["res.config.settings"].create(
            {"payment_reviewer_ids": [Command.set((group.user_ids - self.reviewer).ids)]}
        )
        settings.execute()
        self.assertNotIn(self.reviewer, group.user_ids)
        with self.assertRaises(AccessError):
            self._review(payment, "observed", "Too late", user=self.reviewer)

    def test_who_can_answer(self):
        payment = self._create_payment()
        self._review(payment, "observed", "Explain")
        with self.assertRaises(AccessError):
            payment.with_user(self.reviewer)._review_answer("I'm not the issuer")
        payment.with_user(self.accountant)._review_answer("Answered by a colleague")
        self.assertEqual(payment.review_state, "answered")
        with self.assertRaises(UserError):
            payment.with_user(self.issuer)._review_answer("Nothing left to answer")

    # ------------------------------------------------------------------
    # No accounting side effects
    # ------------------------------------------------------------------

    def test_review_never_writes_the_journal_entry(self):
        payment = self._create_payment()
        move = payment.move_id
        state, lines = payment.state, move.line_ids.read(["account_id", "balance", "reconciled"])
        move_model = self.registry["account.move"]
        original_write = move_model.write
        move_writes = []

        def spy_write(records, vals):
            move_writes.append(vals)
            return original_write(records, vals)

        with patch.object(move_model, "write", spy_write):
            self._review(payment, "observed", "Check")
            payment.with_user(self.issuer)._review_answer("Checked")
            self._review(payment, "reviewed")
        self.assertFalse(move_writes, "Reviewing must never write the payment's journal entry.")
        self.assertEqual(payment.state, state)
        self.assertEqual(move.line_ids.read(["account_id", "balance", "reconciled"]), lines)
