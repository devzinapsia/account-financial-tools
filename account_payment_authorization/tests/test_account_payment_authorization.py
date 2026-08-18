from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

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

    def _create_draft_payment(self, bill, user):
        """Create a draft vendor payment directly on the model, without
        ever calling action_post() -- this is what a payment looks like
        right after a third-party module (e.g. ingadhoc's
        account_payment_pro) drafts it directly, bypassing the standard
        "Register Payment" wizard entirely, before anyone has attempted to
        confirm it. authorization_state stays at its default
        ("not_required") until action_post() actually runs.
        """
        return (
            self.env["account.payment"]
            .with_user(user)
            .create(
                {
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                    "partner_id": bill.partner_id.id,
                    "amount": bill.amount_total,
                    "date": bill.invoice_date,
                    "journal_id": self.company_data["default_journal_bank"].id,
                    "payment_method_line_id": self.outbound_payment_method_line.id,
                    "invoice_ids": [Command.set(bill.ids)],
                }
            )
        )

    def _search_filter_domain(self, filter_name, user):
        """Evaluate one of the "To authorize" / "To authorize by me" search
        filters exactly as the web client would, reading the real,
        currently-resolved search view arch instead of duplicating the
        domain by hand -- so this test breaks if the view's domain
        actually changes, instead of silently drifting from it.
        """
        view = self.env["account.payment"].with_user(user).get_view(view_type="search")
        arch = etree.fromstring(view["arch"])
        node = arch.find(f".//filter[@name='{filter_name}']")
        return safe_eval(node.get("domain"), {"uid": user.id})

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

    def test_authorizer_authorizes_untouched_draft_before_any_confirm_attempt(self):
        """An authorized user can authorize a payment that is still in
        authorization_state "not_required" (its default) because nobody
        has attempted to confirm it yet -- they don't need to wait for a
        first confirm attempt to fail and flip it to "to_authorize".
        """
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._create_draft_payment(bill, self.user_creator)
        self.assertEqual(payment.authorization_state, "not_required")
        self.assertEqual(payment.pending_authorizer_ids, self.user_authorizer)

        payment.with_user(self.user_authorizer).action_authorize_payment()

        self.assertEqual(payment.authorization_state, "authorized")
        self.assertEqual(payment.authorized_by_id, self.user_authorizer)
        self.assertEqual(payment.state, "draft")

    def test_authorizer_rejects_untouched_draft_before_any_confirm_attempt(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._create_draft_payment(bill, self.user_creator)
        self.assertEqual(payment.authorization_state, "not_required")

        wizard = (
            self.env["account.payment.authorization.reject.wizard"]
            .with_user(self.user_authorizer)
            .create({"payment_id": payment.id, "reason": "Wrong vendor"})
        )
        wizard.action_confirm()

        self.assertEqual(payment.authorization_state, "rejected")
        self.assertEqual(payment.state, "draft")

    def test_cannot_reauthorize_or_reject_once_already_authorized(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)
        payment.with_user(self.user_authorizer).action_authorize_payment()

        with self.assertRaises(UserError):
            payment.with_user(self.user_authorizer).action_authorize_payment()

        with self.assertRaises(UserError):
            payment.with_user(self.user_authorizer).action_reject_payment()

    def test_authorizer_unauthorizes_and_can_reauthorize(self):
        """An authorizer can undo a mistaken Authorize click: the payment
        goes back to "to_authorize" (still a draft), and can be authorized
        again afterwards -- by the same or a different authorizer.
        """
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)
        payment.with_user(self.user_authorizer).action_authorize_payment()
        self.assertEqual(payment.authorization_state, "authorized")

        payment.with_user(self.user_authorizer).action_unauthorize_payment()

        self.assertEqual(payment.authorization_state, "to_authorize")
        self.assertFalse(payment.authorized_by_id)
        self.assertEqual(payment.state, "draft")
        messages = payment.message_ids.mapped("body")
        self.assertTrue(
            any("revoked" in (m or "").lower() for m in messages),
            "Expected a chatter message logging the revoked authorization.",
        )
        activity = payment.activity_ids.filtered(lambda a: a.user_id == self.user_creator)
        self.assertTrue(
            activity, "Expected an activity notifying the payment's creator."
        )

        # Can be authorized again afterwards, with no restriction.
        payment.with_user(self.user_authorizer).action_authorize_payment()
        self.assertEqual(payment.authorization_state, "authorized")

    def test_unauthorize_button_only_available_while_draft_and_authorized(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)

        # Not yet authorized: nothing to unauthorize.
        with self.assertRaises(UserError):
            payment.with_user(self.user_authorizer).action_unauthorize_payment()

        payment.with_user(self.user_authorizer).action_authorize_payment()
        payment.with_user(self.user_creator).action_post()
        self.assertEqual(payment.state, "in_process")

        # Already confirmed: no longer a draft, so it can't be undone.
        with self.assertRaises(UserError):
            payment.with_user(self.user_authorizer).action_unauthorize_payment()

    def test_non_authorizer_cannot_unauthorize(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)
        payment.with_user(self.user_authorizer).action_authorize_payment()

        with self.assertRaises(AccessError):
            payment.with_user(self.user_creator).action_unauthorize_payment()

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

    def test_block_payment_scheme_shows_data_review_error_message(self):
        """The error the user sees when trying to confirm a payment blocked
        by an "Always block" policy must point them at fixing the data, not
        the generic "an activity has been assigned" wording used for a
        payment that is genuinely just waiting for someone's approval --
        waiting won't help here, since nobody can ever approve it.
        """
        self.env["account.payment.authorization.scheme"].create(
            {
                "name": "No classification -> never pay",
                "domain": str([("invoice_ids.classification_id", "=", False)]),
                "block_payment": True,
            }
        )
        bill = self._create_posted_bill()  # no classification set

        existing_ids = self.env["account.payment"].search([]).ids
        try:
            self._register_payment(bill, self.user_creator)
            self.fail("Expected a UserError blocking the payment.")
        except UserError as exc:
            message = str(exc)

        self.assertIn("does not comply with the authorization policies", message)
        self.assertNotIn("an activity has been assigned", message.lower())
        payment = self.env["account.payment"].search([("id", "not in", existing_ids)])
        self.assertEqual(len(payment), 1)

    def test_bulk_action_post_combines_both_block_reasons_in_one_error(self):
        """A single action_post() call covering both a permanently-blocked
        payment and a merely-pending-authorization payment (e.g. selecting
        several vendor payments and confirming them together) must mention
        both reasons, not silently drop one.
        """
        self.env["account.payment.authorization.scheme"].create(
            {
                "name": "No classification -> never pay",
                "domain": str([("invoice_ids.classification_id", "=", False)]),
                "block_payment": True,
            }
        )
        blocked_bill = self._create_posted_bill()  # no classification set
        blocked_payment = self._create_draft_payment(blocked_bill, self.user_creator)

        pending_bill = self._create_posted_bill(classification=self.classification_sensitive)
        pending_payment = self._create_draft_payment(pending_bill, self.user_creator)

        payments = blocked_payment | pending_payment
        try:
            payments.with_user(self.user_creator).action_post()
            self.fail("Expected a UserError blocking both payments.")
        except UserError as exc:
            message = str(exc)

        self.assertIn("does not comply with the authorization policies", message)
        self.assertIn("requires authorization", message)

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

    def test_search_filter_to_authorize_by_me_excludes_already_authorized(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment_pending = self._register_payment_blocked(bill, self.user_creator)

        bill_2 = self._create_posted_bill(classification=self.classification_sensitive)
        payment_authorized = self._register_payment_blocked(bill_2, self.user_creator)
        payment_authorized.with_user(self.user_authorizer).action_authorize_payment()

        domain = self._search_filter_domain(
            "authorization_to_authorize_by_me", self.user_authorizer
        )
        results = self.env["account.payment"].with_user(self.user_authorizer).search(domain)

        self.assertIn(payment_pending, results)
        self.assertNotIn(
            payment_authorized,
            results,
            "A payment already authorized by me should drop off my "
            "'To authorize by me' filter, since pending_authorizer_ids "
            "alone doesn't change once a payment is authorized.",
        )

    def test_search_filter_to_authorize_by_me_includes_untouched_draft(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._create_draft_payment(bill, self.user_creator)
        self.assertEqual(payment.authorization_state, "not_required")

        domain = self._search_filter_domain(
            "authorization_to_authorize_by_me", self.user_authorizer
        )
        results = self.env["account.payment"].with_user(self.user_authorizer).search(domain)

        self.assertIn(payment, results)

    def test_search_filter_to_authorize_excludes_authorized_and_rejected(self):
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment_pending = self._register_payment_blocked(bill, self.user_creator)

        bill_2 = self._create_posted_bill(classification=self.classification_sensitive)
        payment_authorized = self._register_payment_blocked(bill_2, self.user_creator)
        payment_authorized.with_user(self.user_authorizer).action_authorize_payment()

        bill_3 = self._create_posted_bill(classification=self.classification_sensitive)
        payment_rejected = self._register_payment_blocked(bill_3, self.user_creator)
        self.env["account.payment.authorization.reject.wizard"].with_user(
            self.user_authorizer
        ).create(
            {"payment_id": payment_rejected.id, "reason": "Not needed"}
        ).action_confirm()

        domain = self._search_filter_domain("authorization_to_authorize", self.user_manager)
        results = self.env["account.payment"].search(domain)

        self.assertIn(payment_pending, results)
        self.assertNotIn(payment_authorized, results)
        self.assertNotIn(payment_rejected, results)

    def test_new_scheme_defaults_to_current_company(self):
        scheme = (
            self.env["account.payment.authorization.scheme"]
            .with_user(self.user_manager)
            .create({"name": "Company default test"})
        )
        self.assertEqual(scheme.company_id, self.env.company)

    def test_new_scheme_domain_defaults_to_pending_vendor_payments(self):
        scheme = self.env["account.payment.authorization.scheme"].create(
            {"name": "Domain default test"}
        )
        domain = safe_eval(scheme.domain)
        self.assertIn(("payment_type", "=", "outbound"), domain)
        self.assertIn(("partner_type", "=", "supplier"), domain)
        self.assertIn(("is_pending_confirmation", "=", True), domain)

    def test_is_pending_confirmation_survives_wizard_premature_state_flip(self):
        """The Register Payment wizard sets payment.state to 'in_process'
        before action_post() ever runs (see the note in action_post()),
        while the underlying journal entry is still draft. A scheme
        condition using is_pending_confirmation (based on move_id.state,
        not the payment's own state) must still correctly match and block
        the payment despite that premature flip -- unlike a condition
        using the payment's own Status field would.
        """
        scheme = self.env["account.payment.authorization.scheme"].create(
            {
                "name": "Pending confirmation scheme",
                "domain": str(
                    [
                        ("invoice_ids.classification_id", "=", self.classification_sensitive.id),
                        ("is_pending_confirmation", "=", True),
                    ]
                ),
                "authorized_user_ids": [Command.set([self.user_authorizer.id])],
            }
        )
        bill = self._create_posted_bill(classification=self.classification_sensitive)
        payment = self._register_payment_blocked(bill, self.user_creator)

        self.assertIn(scheme, payment.matched_scheme_ids)
        self.assertEqual(payment.pending_authorizer_ids, self.user_authorizer)

    def test_is_pending_confirmation_false_once_actually_confirmed(self):
        bill = self._create_posted_bill()
        payment = self._register_payment(bill, self.user_creator)
        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_pending_confirmation)
