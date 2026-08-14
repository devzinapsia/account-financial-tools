from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentAuthorization(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        users_model = cls.env["res.users"].with_context(no_reset_password=True)
        group_invoice = cls.env.ref("account.group_account_invoice")
        group_manager = cls.env.ref("account.group_account_manager")

        cls.user_creator = users_model.create(
            {
                "name": "Payment Creator",
                "login": "payment_creator",
                "email": "payment_creator@test.example.com",
                "group_ids": [Command.set([group_invoice.id])],
            }
        )
        cls.user_authorizer = users_model.create(
            {
                "name": "Payment Authorizer",
                "login": "payment_authorizer",
                "email": "payment_authorizer@test.example.com",
                "group_ids": [Command.set([group_invoice.id])],
            }
        )
        cls.user_authorizer_2 = users_model.create(
            {
                "name": "Payment Authorizer 2",
                "login": "payment_authorizer_2",
                "email": "payment_authorizer_2@test.example.com",
                "group_ids": [Command.set([group_invoice.id])],
            }
        )
        cls.user_manager = users_model.create(
            {
                "name": "Accounting Manager",
                "login": "payment_manager",
                "email": "payment_manager@test.example.com",
                "group_ids": [Command.set([group_manager.id])],
            }
        )

        cls.classification_sensitive = cls.env["account.move.classification"].create(
            {"name": "Sensitive"}
        )
        cls.classification_blocked = cls.env["account.move.classification"].create(
            {"name": "Permanently blocked"}
        )

        cls.scheme_classification = cls.env["account.payment.authorization.scheme"].create(
            {
                "name": "Sensitive bills",
                "domain": str(
                    [("invoice_ids.classification_id", "=", cls.classification_sensitive.id)]
                ),
                "authorized_user_ids": [Command.set([cls.user_authorizer.id])],
            }
        )
        cls.scheme_no_authorizers = cls.env["account.payment.authorization.scheme"].create(
            {
                "name": "Blocked bills (empty authorizers)",
                "domain": str(
                    [("invoice_ids.classification_id", "=", cls.classification_blocked.id)]
                ),
            }
        )

    def _create_posted_bill(self, classification=None, price=100.0):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Test line",
                            "quantity": 1,
                            "price_unit": price,
                        }
                    )
                ],
            }
        )
        if classification:
            bill.classification_id = classification
        bill.action_post()
        return bill

    def _register_payment(self, bill, user):
        wizard = (
            self.env["account.payment.register"]
            .with_user(user)
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"payment_method_line_id": self.outbound_payment_method_line.id})
        )
        return wizard._create_payments()

    def _register_payment_blocked(self, bill, user):
        """Register a payment expected to be blocked pending authorization.
        Returns the created (still draft) account.payment.

        Deliberately does not use `self.assertRaises()`: Odoo's test
        `assertRaises` wraps the call in a cursor savepoint that gets rolled
        back once the expected exception is caught, which would also erase
        the payment record we need to inspect afterwards.
        """
        existing_ids = self.env["account.payment"].search([]).ids
        try:
            self._register_payment(bill, user)
            self.fail("Expected a UserError blocking the payment.")
        except UserError:
            pass
        payment = self.env["account.payment"].search([("id", "not in", existing_ids)])
        self.assertEqual(len(payment), 1)
        return payment

    # -- Scenarios -----------------------------------------------------

    def test_no_scheme_matches_confirms_directly(self):
        bill = self._create_posted_bill()
        payment = self._register_payment(bill, self.user_creator)
        self.assertEqual(payment.authorization_state, "not_required")
        self.assertEqual(payment.state, "in_process")

    def test_scheme_matches_authorized_user_confirms_directly(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment(bill, self.user_authorizer)
        self.assertEqual(payment.authorization_state, "authorized")
        self.assertEqual(payment.authorized_by_id, self.user_authorizer)
        self.assertEqual(payment.state, "in_process")
        messages = payment.message_ids.mapped("body")
        self.assertTrue(
            any("authorized" in (m or "").lower() for m in messages),
            "Expected a chatter message logging the one-step authorize+confirm.",
        )

    def test_scheme_matches_unauthorized_user_blocks_payment(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)
        self.assertEqual(payment.authorization_state, "to_authorize")
        self.assertEqual(payment.state, "draft")
        self.assertEqual(payment.pending_authorizer_ids, self.user_authorizer)
        activity = payment.activity_ids.filtered(
            lambda a: a.user_id == self.user_authorizer
        )
        self.assertTrue(activity)

    def test_authorizer_authorizes_without_confirming(self):
        """The "Authorize" action only sets authorization_state -- it does
        not post the payment. Confirming is a deliberately separate step.
        """
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)

        payment.with_user(self.user_authorizer).action_authorize_payment()

        self.assertEqual(payment.authorization_state, "authorized")
        self.assertEqual(payment.authorized_by_id, self.user_authorizer)
        self.assertEqual(payment.state, "draft")
        self.assertTrue(
            all(
                activity.state == "done" or not activity.exists()
                for activity in payment.activity_ids
            )
        )

    def test_any_user_can_confirm_once_authorized(self):
        """Once authorized (but not yet confirmed), anyone -- not just an
        authorized user -- can finish confirming it with the regular
        Confirm button.
        """
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)
        payment.with_user(self.user_authorizer).action_authorize_payment()
        self.assertEqual(payment.state, "draft")

        # user_creator is not an authorized user for this scheme, but the
        # payment is already authorized, so they can still confirm it.
        payment.with_user(self.user_creator).action_post()

        self.assertEqual(payment.state, "in_process")
        self.assertEqual(payment.authorization_state, "authorized")
        self.assertEqual(payment.authorized_by_id, self.user_authorizer)

    def test_authorization_events_are_logged_in_chatter(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)

        payment.with_user(self.user_authorizer).action_authorize_payment()
        messages = payment.message_ids.mapped("body")
        self.assertTrue(
            any("authorized" in (m or "").lower() for m in messages),
            "Expected a chatter message logging who authorized the payment.",
        )

        payment.with_user(self.user_creator).action_post()
        messages = payment.message_ids.mapped("body")
        self.assertTrue(
            any("confirmed" in (m or "").lower() for m in messages),
            "Expected a chatter message logging who confirmed the payment.",
        )

    def test_authorizer_rejects_payment_with_reason(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)

        wizard = (
            self.env["account.payment.authorization.reject.wizard"]
            .with_user(self.user_authorizer)
            .create({"payment_id": payment.id, "reason": "Missing supporting documents"})
        )
        wizard.action_confirm()

        self.assertEqual(payment.authorization_state, "rejected")
        self.assertEqual(
            payment.authorization_reject_reason, "Missing supporting documents"
        )
        self.assertEqual(payment.state, "draft")
        rejection_activity = payment.activity_ids.filtered(
            lambda a: a.user_id == self.user_creator
        )
        self.assertTrue(rejection_activity)

    def test_scheme_without_authorized_users_blocks_forever(self):
        bill = self._create_posted_bill(classification=self.classification_blocked)
        payment = self._register_payment_blocked(bill, self.user_creator)

        self.assertEqual(payment.authorization_state, "to_authorize")
        self.assertFalse(payment.pending_authorizer_ids)
        self.assertFalse(payment.activity_ids)

        with self.assertRaises(AccessError):
            payment.with_user(self.user_manager).action_authorize_payment()

    def test_two_matching_schemes_union_of_authorizers(self):
        scheme_amount = self.env["account.payment.authorization.scheme"].create(
            {
                "name": "Large amounts",
                "domain": str([("amount", ">=", 50.0)]),
                "authorized_user_ids": [Command.set([self.user_authorizer_2.id])],
            }
        )
        bill = self._create_posted_bill(
            classification=self.classification_sensitive, price=100.0
        )
        payment = self._register_payment_blocked(bill, self.user_creator)

        self.assertEqual(
            payment.pending_authorizer_ids,
            self.user_authorizer | self.user_authorizer_2,
        )
        self.assertIn(scheme_amount, payment.matched_scheme_ids)
        self.assertIn(self.scheme_classification, payment.matched_scheme_ids)

        # The authorizer of the *other* scheme can approve too.
        payment.with_user(self.user_authorizer_2).action_authorize_payment()
        self.assertEqual(payment.authorization_state, "authorized")

    def test_customer_payment_never_triggers_authorization(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
                "invoice_line_ids": [
                    Command.create(
                        {"name": "Test line", "quantity": 1, "price_unit": 500.0}
                    )
                ],
            }
        )
        invoice.classification_id = self.classification_sensitive
        invoice.action_post()

        wizard = (
            self.env["account.payment.register"]
            .with_user(self.user_creator)
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"payment_method_line_id": self.inbound_payment_method_line.id})
        )
        payments = wizard._create_payments()

        self.assertEqual(payments.authorization_state, "not_required")
        # Confirmed straight away regardless of the account type behind the
        # outstanding account (some journal setups jump straight to 'paid').
        self.assertIn(payments.state, ("in_process", "paid"))

    def test_block_payment_scheme_ignores_authorized_users(self):
        # Deliberately give this "always block" scheme some authorized
        # users: block_payment must still win, they must never be able to
        # approve. This matches the example: no classification -> blocked.
        scheme_block = self.env["account.payment.authorization.scheme"].create(
            {
                "name": "No classification -> never pay",
                "domain": str([("invoice_ids.classification_id", "=", False)]),
                "block_payment": True,
                "authorized_user_ids": [Command.set([self.user_authorizer.id])],
            }
        )
        bill = self._create_posted_bill()  # no classification set
        payment = self._register_payment_blocked(bill, self.user_creator)

        self.assertIn(scheme_block, payment.matched_scheme_ids)
        self.assertFalse(payment.pending_authorizer_ids)
        self.assertFalse(payment.activity_ids)

        with self.assertRaises(AccessError):
            payment.with_user(self.user_authorizer).action_authorize_payment()

    def test_amount_tier_domain_schemes(self):
        scheme_low = self.env["account.payment.authorization.scheme"].create(
            {
                "name": "0 to 1000",
                "domain": str([("amount", ">=", 0), ("amount", "<", 1000)]),
                "authorized_user_ids": [Command.set([self.user_authorizer.id])],
            }
        )
        scheme_high = self.env["account.payment.authorization.scheme"].create(
            {
                "name": "1000 and above",
                "domain": str([("amount", ">=", 1000)]),
                "authorized_user_ids": [Command.set([self.user_authorizer_2.id])],
            }
        )

        low_bill = self._create_posted_bill(price=500.0)
        low_payment = self._register_payment_blocked(low_bill, self.user_creator)
        self.assertIn(scheme_low, low_payment.matched_scheme_ids)
        self.assertNotIn(scheme_high, low_payment.matched_scheme_ids)
        self.assertEqual(low_payment.pending_authorizer_ids, self.user_authorizer)

        high_bill = self._create_posted_bill(price=1500.0)
        high_payment = self._register_payment_blocked(high_bill, self.user_creator)
        self.assertIn(scheme_high, high_payment.matched_scheme_ids)
        self.assertNotIn(scheme_low, high_payment.matched_scheme_ids)
        self.assertEqual(high_payment.pending_authorizer_ids, self.user_authorizer_2)

    def test_non_authorizer_cannot_approve_or_reject(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)

        with self.assertRaises(AccessError):
            payment.with_user(self.user_creator).action_authorize_payment()

        with self.assertRaises(AccessError):
            payment.with_user(self.user_creator).action_reject_payment()

        with self.assertRaises(AccessError):
            self.env["account.payment.authorization.reject.wizard"].with_user(
                self.user_creator
            ).create({"payment_id": payment.id, "reason": "Not allowed"}).action_confirm()
