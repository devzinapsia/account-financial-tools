from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountVendorBillAuthorization(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Chatter messages are rendered in the acting user's language; pin it
        # so the assertions on their text don't depend on which languages
        # happen to be loaded in the database.
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.env.user.lang = "en_US"

        users_model = cls.env["res.users"].with_context(no_reset_password=True)
        group_invoice = cls.env.ref("account.group_account_invoice")
        group_manager = cls.env.ref("account.group_account_manager")

        def create_user(login, name, group):
            return users_model.create(
                {
                    "name": name,
                    "login": login,
                    "email": f"{login}@test.example.com",
                    "lang": "en_US",
                    "group_ids": [Command.set([group.id])],
                }
            )

        cls.user_creator = create_user("bill_creator", "Bill Creator", group_invoice)
        cls.user_authorizer = create_user("bill_authorizer", "Bill Authorizer", group_invoice)
        cls.user_authorizer_2 = create_user("bill_authorizer_2", "Bill Authorizer 2", group_invoice)
        cls.user_other = create_user("bill_other", "Other Billing User", group_invoice)
        cls.user_manager = create_user("bill_manager", "Accounting Manager", group_manager)

        classification_model = cls.env["account.move.classification"]
        cls.classification_sensitive = classification_model.create({"name": "Sensitive"})
        cls.classification_two = classification_model.create({"name": "Two authorizers"})
        cls.classification_blocked = classification_model.create({"name": "Empty authorizers"})

        policy_model = cls.env["account.vendor.bill.authorization.policy"]
        cls.policy_sensitive = policy_model.create(
            {
                "name": "Sensitive bills",
                "domain": str([("classification_id", "=", cls.classification_sensitive.id)]),
                "authorized_user_ids": [Command.set([cls.user_authorizer.id])],
            }
        )
        cls.policy_two = policy_model.create(
            {
                "name": "Bills needing one of two authorizers",
                "domain": str([("classification_id", "=", cls.classification_two.id)]),
                "authorized_user_ids": [
                    Command.set([cls.user_authorizer.id, cls.user_authorizer_2.id])
                ],
            }
        )
        cls.policy_no_authorizers = policy_model.create(
            {
                "name": "Blocked bills (empty authorizers)",
                "domain": str([("classification_id", "=", cls.classification_blocked.id)]),
            }
        )

    # -- Helpers --------------------------------------------------------

    def _create_bill(self, classification=None, move_type="in_invoice", partner=None,
                     price=100.0, user=None):
        vals = {
            "move_type": move_type,
            "journal_id": self.company_data["default_journal_purchase"].id,
            "partner_id": (partner or self.partner_a).id,
            "invoice_date": "2026-01-01",
            "invoice_line_ids": [
                Command.create({"name": "Test line", "quantity": 1, "price_unit": price})
            ],
        }
        if classification:
            vals["classification_id"] = classification.id
        return self.env["account.move"].with_user(user or self.user_creator).create(vals)

    def _create_posted_bill(self, classification=None, user=None, **kwargs):
        bill = self._create_bill(classification, user=user, **kwargs)
        bill.with_user(user or self.user_creator).action_post()
        self.assertEqual(bill.state, "posted")
        return bill

    def _register_payment(self, bill, user, amount=None):
        vals = {"amount": amount} if amount else {}
        wizard = (
            self.env["account.payment.register"]
            .with_user(user)
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create(vals)
        )
        return wizard._create_payments()

    def _assert_payment_blocked(self, bill, user=None):
        user = user or self.user_other
        with self.assertRaises(UserError):
            bill.with_user(user).action_register_payment()
        with self.assertRaises(UserError):
            bill.with_user(user).action_force_register_payment()
        with self.assertRaises(UserError):
            self._register_payment(bill, user)
        self.assertEqual(bill.payment_state, "not_paid")

    def _search_filter_domain(self, filter_name, user):
        """Evaluate one of the authorization search filters exactly as the
        web client would, reading the real, currently-resolved bills search
        view arch instead of duplicating the domain by hand.
        """
        view = (
            self.env["account.move"]
            .with_user(user)
            .get_view(view_id=self.env.ref("account.view_account_bill_filter").id, view_type="search")
        )
        node = etree.fromstring(view["arch"]).find(f".//filter[@name='{filter_name}']")
        return safe_eval(node.get("domain"), {"uid": user.id})

    def _requests(self, bill):
        return bill._get_authorization_requests()

    def _todo_activities(self, bill):
        return bill.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref("mail.mail_activity_data_todo")
        )

    def _bodies(self, bill):
        return [body or "" for body in bill.message_ids.mapped("body")]

    # -- Confirmation ---------------------------------------------------

    def test_no_policy_matches_confirms_and_can_be_paid(self):
        bill = self._create_posted_bill()
        self.assertEqual(bill.authorization_state, "not_required")
        self._register_payment(bill, self.user_other)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))

    def test_draft_matching_bill_is_not_pending_yet(self):
        """Authorization happens once the bill is confirmed."""
        bill = self._create_bill(self.classification_sensitive)
        self.assertEqual(bill.matched_policy_ids, self.policy_sensitive)
        self.assertEqual(bill.authorization_state, "not_required")
        self.assertFalse(self._requests(bill))

    def test_confirming_matching_bill_requests_authorization(self):
        """Anyone can confirm; the bill is then pending authorization and
        every authorizer is asked through an activity.
        """
        bill = self._create_posted_bill(self.classification_two)
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertEqual(self._requests(bill).user_id, self.user_authorizer | self.user_authorizer_2)
        self.assertEqual(len(self._requests(bill)), 2)
        self.assertTrue(any("Authorization requested from" in b for b in self._bodies(bill)))

    def test_confirming_as_authorizer_does_not_authorize_implicitly(self):
        bill = self._create_posted_bill(self.classification_sensitive, user=self.user_authorizer)
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertFalse(bill.authorized_by_id)

    def test_always_block_policy_prevents_confirming(self):
        policy_block = self.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Never pay partner B",
                "domain": str([("partner_id", "=", self.partner_b.id)]),
                "always_block": True,
                "authorized_user_ids": [Command.set([self.user_authorizer_2.id])],
            }
        )
        bill = self._create_bill(self.classification_sensitive, partner=self.partner_b)
        self.assertTrue(bill.is_blocked)
        # Authorizers of a blocking policy are ignored.
        self.assertEqual(bill.pending_authorizer_ids, self.user_authorizer)
        for user in (self.user_creator, self.user_authorizer, self.env.user):
            with self.assertRaises(UserError) as error:
                bill.with_user(user).action_post()
            self.assertIn(policy_block.name, str(error.exception))
        self.assertEqual(bill.state, "draft")

    def test_always_block_also_applies_to_the_post_entries_action(self):
        self.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Never pay partner B",
                "domain": str([("partner_id", "=", self.partner_b.id)]),
                "always_block": True,
            }
        )
        bill = self._create_bill(partner=self.partner_b)
        wizard = (
            self.env["validate.account.move"]
            .with_user(self.user_creator)
            .create({"move_ids": [Command.set(bill.ids)]})
        )
        with self.assertRaises(UserError):
            wizard.validate_move()
        self.assertEqual(bill.state, "draft")

    def test_post_entries_action_requests_authorization_too(self):
        bill = self._create_bill(self.classification_sensitive)
        self.env["validate.account.move"].with_user(self.user_creator).create(
            {"move_ids": [Command.set(bill.ids)]}
        ).validate_move()
        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertTrue(self._requests(bill))

    def test_policy_without_authorizers_can_never_be_authorized(self):
        bill = self._create_posted_bill(self.classification_blocked)
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertFalse(bill.pending_authorizer_ids)
        self.assertFalse(self._requests(bill))
        self.assertTrue(any("no authorized users configured" in b for b in self._bodies(bill)))
        for user in (self.user_authorizer, self.user_manager, self.env.user):
            with self.assertRaises(AccessError):
                bill.with_user(user).action_authorize_bill()
            with self.assertRaises(AccessError):
                bill.with_user(user).action_reject_bill()
        self._assert_payment_blocked(bill)

    def test_two_matching_policies_union_of_authorizers(self):
        policy_partner = self.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Partner B bills",
                "domain": str([("partner_id", "=", self.partner_b.id)]),
                "authorized_user_ids": [Command.set([self.user_authorizer_2.id])],
            }
        )
        for authorizer in (self.user_authorizer, self.user_authorizer_2):
            with self.subTest(authorizer=authorizer.login):
                bill = self._create_posted_bill(self.classification_sensitive, partner=self.partner_b)
                self.assertEqual(bill.matched_policy_ids, self.policy_sensitive | policy_partner)
                self.assertEqual(
                    bill.pending_authorizer_ids, self.user_authorizer | self.user_authorizer_2
                )
                bill.with_user(authorizer).action_authorize_bill()
                self.assertEqual(bill.authorization_state, "authorized")
                self.assertEqual(bill.authorized_by_id, authorizer)

    def test_customer_invoice_never_triggers_authorization(self):
        self.env["account.vendor.bill.authorization.policy"].create(
            {"name": "Catch-all", "domain": "[]"}
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
                "invoice_line_ids": [
                    Command.create({"name": "Test line", "quantity": 1, "price_unit": 100.0})
                ],
            }
        )
        invoice.with_user(self.user_creator).action_post()
        self.assertFalse(invoice.matched_policy_ids)
        self.assertEqual(invoice.authorization_state, "not_required")
        self._register_payment(invoice, self.user_other)
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))

    def test_policy_change_is_not_retroactive_on_confirmed_bills(self):
        """Whether a bill requires authorization is decided when it is
        confirmed: bills confirmed before a policy existed stay payable.
        """
        bill = self._create_posted_bill()
        self.env["account.vendor.bill.authorization.policy"].create(
            {"name": "Catch-all", "domain": "[]", "authorized_user_ids": [Command.set([self.user_authorizer.id])]}
        )
        self._register_payment(bill, self.user_other)
        self.assertEqual(bill.authorization_state, "not_required")
        self.assertIn(bill.payment_state, ("paid", "in_payment"))

    # -- Payment blocking -------------------------------------------------

    def test_bill_to_authorize_cannot_be_paid(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        self._assert_payment_blocked(bill)
        # Not even by an authorizer, before authorizing.
        self._assert_payment_blocked(bill, self.user_authorizer)

    def test_reconciliation_safety_net(self):
        """Any reconciliation of the bill's payable line is refused, e.g. a
        payment registered elsewhere and matched by hand.
        """
        bill = self._create_posted_bill(self.classification_sensitive)
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": bill.partner_id.id,
                "amount": bill.amount_total,
                "journal_id": self.company_data["default_journal_bank"].id,
                "payment_method_line_id": self.outbound_payment_method_line.id,
            }
        )
        payment.action_post()
        lines = (bill.line_ids | payment.move_id.line_ids).filtered(
            lambda line: line.account_id == bill.line_ids.filtered(
                lambda l: l.account_type == "liability_payable"
            ).account_id
        )
        with self.assertRaises(UserError):
            lines.reconcile()
        self.assertEqual(bill.payment_state, "not_paid")

    def test_outstanding_credit_cannot_be_applied(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        refund = self._create_posted_bill(move_type="in_refund", price=40.0)
        self.assertEqual(refund.authorization_state, "not_required")
        refund_line = refund.line_ids.filtered(lambda l: l.account_type == "liability_payable")
        with self.assertRaises(UserError):
            bill.js_assign_outstanding_line(refund_line.id)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        bill.js_assign_outstanding_line(refund_line.id)
        self.assertEqual(bill.payment_state, "partial")

    def test_authorize_then_anyone_can_pay(self):
        bill = self._create_posted_bill(self.classification_two)
        messages_before = bill.message_ids
        unrelated = bill.activity_schedule(
            "mail.mail_activity_data_todo", summary="Call the vendor", user_id=self.user_creator.id
        )

        bill.with_user(self.user_authorizer).action_authorize_bill()

        self.assertEqual(bill.authorization_state, "authorized")
        self.assertEqual(bill.authorized_by_id, self.user_authorizer)
        self.assertFalse(self._requests(bill))
        self.assertTrue(unrelated.exists())
        new_messages = bill.message_ids - messages_before
        self.assertEqual(len(new_messages), 1, new_messages.mapped("body"))
        self.assertIn("It can now be paid", new_messages.body)
        self.assertFalse(new_messages.mail_activity_type_id)

        self._register_payment(bill, self.user_other)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))

    def test_rejected_bill_cannot_be_paid(self):
        bill = self._create_posted_bill(self.classification_two)
        action = bill.with_user(self.user_authorizer).action_reject_bill()
        self.env[action["res_model"]].with_user(self.user_authorizer).with_context(
            **action["context"]
        ).create({"reason": "Wrong amount"}).action_confirm()

        self.assertEqual(bill.authorization_state, "rejected")
        self.assertEqual(bill.authorization_reject_reason, "Wrong amount")
        self.assertFalse(self._requests(bill))
        notice = self._todo_activities(bill)
        self.assertEqual(notice.user_id, self.user_creator)
        self.assertIn("Wrong amount", str(notice.note))
        self.assertTrue(any("Reason: Wrong amount" in b for b in self._bodies(bill)))
        self._assert_payment_blocked(bill)
        with self.assertRaises(UserError):
            bill.with_user(self.user_authorizer).action_authorize_bill()

    def test_rejected_bill_fixed_and_confirmed_again_requests_authorization(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer)._reject_bill("Wrong amount")
        bill.button_draft()
        self.assertEqual(bill.authorization_state, "not_required")
        bill.write({"invoice_line_ids": [Command.update(bill.invoice_line_ids.id, {"price_unit": 50.0})]})
        bill.with_user(self.user_creator).action_post()
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertTrue(self._requests(bill))

    def test_full_reversal_of_bill_awaiting_authorization_is_allowed(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        reversal = (
            self.env["account.move.reversal"]
            .with_user(self.user_creator)
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"journal_id": bill.journal_id.id, "reason": "Cancel it"})
        )
        reversal.modify_moves()
        refund = bill.reversal_move_ids
        self.assertEqual(refund.state, "posted")
        self.assertEqual(refund.authorization_state, "not_required")
        self.assertEqual(bill.payment_state, "reversed")

    def test_vendor_refund_requires_authorization_too(self):
        refund = self._create_posted_bill(self.classification_sensitive, move_type="in_refund")
        self.assertEqual(refund.authorization_state, "to_authorize")
        self.assertTrue(self._requests(refund))
        self._assert_payment_blocked(refund)
        refund.with_user(self.user_authorizer).action_authorize_bill()
        self._register_payment(refund, self.user_other)
        self.assertIn(refund.payment_state, ("paid", "in_payment"))

    def test_refund_awaiting_authorization_cannot_be_applied_to_a_bill(self):
        bill = self._create_posted_bill()
        refund = self._create_posted_bill(self.classification_sensitive, move_type="in_refund", price=40.0)
        refund_line = refund.line_ids.filtered(lambda l: l.account_type == "liability_payable")
        with self.assertRaises(UserError):
            bill.js_assign_outstanding_line(refund_line.id)

    # -- Authorization lifecycle ----------------------------------------

    def test_unauthorize_only_while_unpaid(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()

        # Any current pending authorizer can unauthorize, not only the one
        # who authorized it.
        self.policy_sensitive.authorized_user_ids = [Command.link(self.user_authorizer_2.id)]
        bill.with_user(self.user_authorizer_2).action_unauthorize_bill()
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertFalse(bill.authorized_by_id)
        self.assertEqual(self._todo_activities(bill).filtered(lambda a: a.user_id == self.user_creator).user_id,
                         self.user_creator)
        self._assert_payment_blocked(bill)

        bill.with_user(self.user_authorizer).action_authorize_bill()
        self._register_payment(bill, self.user_other, amount=30.0)
        self.assertEqual(bill.payment_state, "partial")
        with self.assertRaises(UserError):
            bill.with_user(self.user_authorizer).action_unauthorize_bill()

    def test_non_authorizer_cannot_authorize_reject_or_unauthorize(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        with self.assertRaises(AccessError):
            bill.with_user(self.user_other).action_authorize_bill()
        with self.assertRaises(AccessError):
            bill.with_user(self.user_other).action_reject_bill()
        bill.with_user(self.user_authorizer).action_authorize_bill()
        with self.assertRaises(AccessError):
            bill.with_user(self.user_other).action_unauthorize_bill()

    def test_reject_wizard_rechecks_permission_server_side(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        wizard = (
            self.env["account.vendor.bill.authorization.reject.wizard"]
            .with_user(self.user_other)
            .create({"move_id": bill.id, "reason": "Not mine to reject"})
        )
        with self.assertRaises(AccessError):
            wizard.action_confirm()

    def test_draft_bill_cannot_be_authorized(self):
        bill = self._create_bill(self.classification_sensitive)
        with self.assertRaises(UserError):
            bill.with_user(self.user_authorizer).action_authorize_bill()

    def test_reset_to_draft_requires_authorization_again(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()

        bill.button_draft()

        self.assertEqual(bill.authorization_state, "not_required")
        self.assertFalse(bill.authorized_by_id)
        self.assertTrue(any("was reset to draft" in b for b in self._bodies(bill)))
        bill.with_user(self.user_creator).action_post()
        self.assertEqual(bill.authorization_state, "to_authorize")
        self._assert_payment_blocked(bill)

    def test_reset_to_draft_and_cancel_remove_requests(self):
        bill = self._create_posted_bill(self.classification_two)
        self.assertTrue(self._requests(bill))
        bill.button_draft()
        self.assertFalse(self._requests(bill))
        bill.button_cancel()
        self.assertEqual(bill.state, "cancel")

    def test_editing_authorized_confirmed_bill_requests_authorization_again(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        bill.with_user(self.user_creator).classification_id = self.classification_two
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertEqual(bill.matched_policy_ids, self.policy_two)
        self.assertEqual(self._requests(bill).user_id, self.user_authorizer | self.user_authorizer_2)
        self.assertTrue(any("Authorization reset" in b for b in self._bodies(bill)))
        self._assert_payment_blocked(bill)

    def test_editing_confirmed_bill_out_of_every_policy_makes_it_payable(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer)._reject_bill("No")
        bill.with_user(self.user_creator).classification_id = False
        self.assertEqual(bill.authorization_state, "not_required")
        self.assertFalse(self._requests(bill))

    def test_authorization_survives_edit_to_non_sensitive_field(self):
        bill = self._create_posted_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        bill.with_user(self.user_creator).ref = "SUPPLIER-REF-1"
        self.assertEqual(bill.authorization_state, "authorized")

    def test_draft_authorized_under_the_old_flow_stays_authorized(self):
        """Left over from versions that authorized before confirming."""
        bill = self._create_bill(self.classification_sensitive)
        bill.write({"authorization_state": "authorized", "authorized_by_id": self.user_authorizer.id})
        bill.with_user(self.user_other).action_post()
        self.assertEqual(bill.authorization_state, "authorized")
        self.assertFalse(self._requests(bill))
        self.assertTrue(any("authorized earlier by" in b for b in self._bodies(bill)))
        self._register_payment(bill, self.user_other)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))

    def test_requests_in_another_language_are_recognized(self):
        lang = self.env["res.lang"]._activate_lang("es_AR")
        bill = self._create_bill(self.classification_sensitive)
        bill.with_context(lang=lang.code).with_user(self.user_creator).action_post()
        self.assertEqual(len(self._requests(bill)), 1)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        self.assertFalse(self._requests(bill))

    def test_cleanup_stale_authorization_requests(self):
        summary = "Vendor bill authorization requested"

        def schedule(bill, user):
            return bill.activity_schedule(
                "mail.mail_activity_data_todo", summary=summary, user_id=user.id
            )

        draft = self._create_bill(self.classification_sensitive)
        stale = schedule(draft, self.user_authorizer)

        pending = self._create_posted_bill(self.classification_two)
        first, other = self._requests(pending).sorted("id")
        duplicate = schedule(pending, first.user_id)
        unrelated = pending.activity_schedule(
            "mail.mail_activity_data_todo", summary="Call the vendor", user_id=self.user_authorizer.id
        )

        removed = self.env["account.move"]._cleanup_stale_authorization_requests()

        self.assertEqual(removed, 2)
        self.assertFalse(stale.exists())
        self.assertFalse(duplicate.exists())
        self.assertTrue(first.exists())
        self.assertTrue(other.exists())
        self.assertTrue(unrelated.exists())

    def test_always_true_leaf_in_policy_domain(self):
        """The 19.0.2.0.0 migration replaces the old Status conditions by an
        always-true leaf: such a domain must keep matching.
        """
        self.policy_sensitive.domain = str(
            [(1, "=", 1), ("classification_id", "=", self.classification_sensitive.id)]
        )
        bill = self._create_posted_bill(self.classification_sensitive)
        self.assertEqual(bill.matched_policy_ids, self.policy_sensitive)
        self.assertEqual(bill.authorization_state, "to_authorize")

    # -- Views --------------------------------------------------------------

    def test_search_filters(self):
        bill_pending = self._create_posted_bill(self.classification_sensitive)
        bill_other_authorizer = self._create_posted_bill(self.classification_two)
        bill_authorized = self._create_posted_bill(self.classification_sensitive)
        bill_authorized.with_user(self.user_authorizer).action_authorize_bill()
        bill_paid = self._create_posted_bill(self.classification_sensitive)
        bill_paid.with_user(self.user_authorizer).action_authorize_bill()
        self._register_payment(bill_paid, self.user_other)
        bill_rejected = self._create_posted_bill(self.classification_sensitive)
        bill_rejected.with_user(self.user_authorizer)._reject_bill("No")
        bill_draft = self._create_bill(self.classification_sensitive)
        bill_no_authorizers = self._create_posted_bill(self.classification_blocked)
        bills = (
            bill_pending | bill_other_authorizer | bill_authorized | bill_paid
            | bill_rejected | bill_draft | bill_no_authorizers
        )

        def search(filter_name, user):
            domain = self._search_filter_domain(filter_name, user)
            return self.env["account.move"].with_user(user).search(domain) & bills

        self.assertEqual(
            search("authorization_to_authorize", self.user_creator),
            bill_pending | bill_other_authorizer,
        )
        self.assertEqual(
            search("authorization_to_authorize_by_me", self.user_authorizer_2),
            bill_other_authorizer,
        )
        self.assertEqual(
            search("authorization_authorized_pending_payment", self.user_creator),
            bill_authorized,
        )

    def test_authorization_column_in_bill_and_refund_lists(self):
        for view_xmlid in ("account.view_in_invoice_bill_tree", "account.view_in_invoice_refund_tree"):
            with self.subTest(view=view_xmlid):
                view = self.env["account.move"].get_view(
                    view_id=self.env.ref(view_xmlid).id, view_type="list"
                )
                node = etree.fromstring(view["arch"]).find(".//field[@name='authorization_state']")
                self.assertIsNotNone(node)
                self.assertEqual(node.get("optional"), "hide")

    def test_form_header_hides_pay_while_awaiting_authorization(self):
        view = self.env["account.move"].get_view(
            view_id=self.env.ref("account.view_move_form").id, view_type="form"
        )
        header = etree.fromstring(view["arch"]).find(".//header")
        condition = (
            "(move_type in ('in_invoice', 'in_refund') "
            "and authorization_state in ('to_authorize', 'rejected'))"
        )
        for button_id in ("account_invoice_payment_btn", "account_invoice_payment_secondary_btn"):
            button = header.find(f".//button[@id='{button_id}']")
            self.assertIn(condition, button.get("invisible"))
        names = [button.get("name") for button in header.iter("button")]
        for name in ("action_authorize_bill", "action_reject_bill", "action_unauthorize_bill"):
            self.assertIn(name, names)
        self.assertNotIn("action_authorize_and_confirm_bill", names)
        confirm = [b for b in header.iter("button") if b.get("name") == "action_post"][-1]
        self.assertNotIn("pending_authorizer_ids", confirm.get("invisible"))

    # -- Multi-company -------------------------------------------------

    def _create_company_2_bill(self, company_data, classification):
        return (
            self.env["account.move"]
            .with_company(company_data["company"])
            .create(
                {
                    "move_type": "in_invoice",
                    "journal_id": company_data["default_journal_purchase"].id,
                    "partner_id": self.partner_a.id,
                    "invoice_date": "2026-01-01",
                    "classification_id": classification.id,
                    "invoice_line_ids": [
                        Command.create({"name": "Test line", "quantity": 1, "price_unit": 100.0})
                    ],
                }
            )
        )

    def test_company_policy_only_applies_to_its_own_company(self):
        company_data_2 = self.setup_other_company()
        company_2 = company_data_2["company"]
        classification = self.env["account.move.classification"].create({"name": "Company 2 only"})
        policy_company_2 = self.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Company 2 policy",
                "company_id": company_2.id,
                "domain": str([("classification_id", "=", classification.id)]),
                "authorized_user_ids": [Command.set([self.user_authorizer.id])],
            }
        )

        bill_company_1 = self._create_posted_bill(classification)
        self.assertFalse(bill_company_1.matched_policy_ids)
        self.assertEqual(bill_company_1.authorization_state, "not_required")

        bill_company_2 = self._create_company_2_bill(company_data_2, classification)
        bill_company_2.with_company(company_2).action_post()
        self.assertEqual(bill_company_2.matched_policy_ids, policy_company_2)
        self.assertEqual(bill_company_2.authorization_state, "to_authorize")

    def test_policy_without_company_applies_to_every_company(self):
        company_data_2 = self.setup_other_company()
        classification = self.env["account.move.classification"].create({"name": "Shared"})
        shared_policy = self.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Shared policy",
                "company_id": False,
                "domain": str([("classification_id", "=", classification.id)]),
                "authorized_user_ids": [Command.set([self.user_authorizer.id])],
            }
        )
        self.assertEqual(self._create_bill(classification).matched_policy_ids, shared_policy)
        self.assertEqual(
            self._create_company_2_bill(company_data_2, classification).matched_policy_ids,
            shared_policy,
        )

    def test_policies_of_other_companies_are_hidden_by_record_rule(self):
        company_data_2 = self.setup_other_company()
        policy_company_2 = self.env["account.vendor.bill.authorization.policy"].create(
            {"name": "Company 2 policy", "company_id": company_data_2["company"].id}
        )
        visible = self.env["account.vendor.bill.authorization.policy"].with_user(self.user_manager).search([])
        self.assertNotIn(policy_company_2, visible)
        self.assertIn(self.policy_sensitive, visible)

    def test_new_policy_defaults(self):
        policy = self.env["account.vendor.bill.authorization.policy"].create({"name": "Defaults"})
        self.assertEqual(policy.company_id, self.env.company)
        self.assertEqual(safe_eval(policy.domain), [("move_type", "in", ["in_invoice", "in_refund"])])
