from unittest.mock import patch

from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.modules import module as odoo_module
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

    def _post_blocked(self, bill, user):
        """Attempt to confirm ``bill`` as ``user``, expecting it to be
        blocked.

        Deliberately does not use `self.assertRaises()`: Odoo's test
        `assertRaises` wraps the call in a cursor savepoint that gets rolled
        back once the expected exception is caught, which would also erase
        the authorization state, activities and messages we need to inspect
        afterwards.
        """
        try:
            bill.with_user(user).action_post()
            self.fail("Expected a UserError blocking the vendor bill.")
        except UserError as error:
            return error

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

    def _authorization_activities(self, bill):
        return bill.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref("mail.mail_activity_data_todo")
        )

    # -- Scenarios ------------------------------------------------------

    def test_no_policy_matches_confirms_directly(self):
        bill = self._create_bill()
        self.assertEqual(bill.authorization_state, "not_required")
        bill.with_user(self.user_creator).action_post()
        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.authorization_state, "not_required")

    def test_untouched_draft_already_shows_to_authorize(self):
        bill = self._create_bill(self.classification_sensitive)
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertEqual(bill.matched_policy_ids, self.policy_sensitive)
        self.assertEqual(bill.pending_authorizer_ids, self.user_authorizer)
        self.assertFalse(bill.is_blocked)

    def test_policy_matches_authorized_user_confirms_directly(self):
        bill = self._create_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_post()
        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.authorization_state, "authorized")
        self.assertEqual(bill.authorized_by_id, self.user_authorizer)
        self.assertTrue(
            any("authorized and confirmed directly" in (m or "") for m in bill.message_ids.mapped("body"))
        )

    def test_policy_matches_unauthorized_user_blocks_bill(self):
        bill = self._create_bill(self.classification_two)
        error = self._post_blocked(bill, self.user_creator)
        self.assertIn("requires authorization", str(error))
        self.assertEqual(bill.state, "draft")
        self.assertEqual(bill.authorization_state, "to_authorize")
        activities = self._authorization_activities(bill)
        self.assertEqual(activities.user_id, self.user_authorizer | self.user_authorizer_2)
        self.assertEqual(len(activities), 2)
        self.assertTrue(
            any("Authorization requested from" in (m or "") for m in bill.message_ids.mapped("body"))
        )

    def test_authorizer_authorizes_without_confirming(self):
        bill = self._create_bill(self.classification_sensitive)
        self._post_blocked(bill, self.user_creator)

        bill.with_user(self.user_authorizer).action_authorize_bill()

        self.assertEqual(bill.authorization_state, "authorized")
        self.assertEqual(bill.authorized_by_id, self.user_authorizer)
        self.assertEqual(bill.state, "draft")
        self.assertFalse(self._authorization_activities(bill))

    def test_non_authorizer_confirms_after_authorization(self):
        bill = self._create_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()

        bill.with_user(self.user_other).action_post()

        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.authorization_state, "authorized")
        self.assertEqual(bill.authorized_by_id, self.user_authorizer)
        self.assertTrue(
            any("authorized earlier by" in (m or "") for m in bill.message_ids.mapped("body"))
        )

    def test_authorize_and_confirm_in_one_step(self):
        bill = self._create_bill(self.classification_sensitive)
        self._post_blocked(bill, self.user_creator)

        bill.with_user(self.user_authorizer).action_authorize_and_confirm_bill()

        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.authorization_state, "authorized")
        self.assertEqual(bill.authorized_by_id, self.user_authorizer)
        self.assertFalse(self._authorization_activities(bill))

    def test_authorizer_rejects_with_reason(self):
        bill = self._create_bill(self.classification_sensitive)
        self._post_blocked(bill, self.user_creator)

        action = bill.with_user(self.user_authorizer).action_reject_bill()
        wizard = (
            self.env[action["res_model"]]
            .with_user(self.user_authorizer)
            .with_context(**action["context"])
            .create({"reason": "Wrong amount"})
        )
        wizard.action_confirm()

        self.assertEqual(bill.authorization_state, "rejected")
        self.assertEqual(bill.authorization_reject_reason, "Wrong amount")
        self.assertEqual(bill.state, "draft")
        creator_activity = self._authorization_activities(bill).filtered(
            lambda a: a.user_id == self.user_creator
        )
        self.assertEqual(len(creator_activity), 1)
        self.assertIn("Wrong amount", str(creator_activity.note))
        self.assertFalse(
            self._authorization_activities(bill).filtered(lambda a: a.user_id == self.user_authorizer)
        )
        self.assertTrue(
            any("Reason: Wrong amount" in (m or "") for m in bill.message_ids.mapped("body"))
        )

    def test_reject_wizard_rechecks_permission_server_side(self):
        bill = self._create_bill(self.classification_sensitive)
        wizard = (
            self.env["account.vendor.bill.authorization.reject.wizard"]
            .with_user(self.user_other)
            .create({"move_id": bill.id, "reason": "Not mine to reject"})
        )
        with self.assertRaises(AccessError):
            wizard.action_confirm()

    def test_policy_without_authorizers_blocks_forever(self):
        bill = self._create_bill(self.classification_blocked)
        self._post_blocked(bill, self.user_creator)
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertFalse(bill.pending_authorizer_ids)
        self.assertFalse(self._authorization_activities(bill))
        for user in (self.user_authorizer, self.user_manager, self.env.user):
            with self.assertRaises(AccessError):
                bill.with_user(user).action_authorize_bill()
            with self.assertRaises(AccessError):
                bill.with_user(user).action_authorize_and_confirm_bill()
            with self.assertRaises(AccessError):
                bill.with_user(user).action_reject_bill()
        self._post_blocked(bill, self.user_authorizer)
        self.assertEqual(bill.state, "draft")

    def test_always_block_wins_over_other_matching_policy(self):
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
        self.assertEqual(bill.matched_policy_ids, self.policy_sensitive | policy_block)
        # Authorizers of a blocking policy are ignored.
        self.assertEqual(bill.pending_authorizer_ids, self.user_authorizer)

        error = self._post_blocked(bill, self.user_authorizer)
        self.assertIn(policy_block.name, str(error))
        self.assertFalse(self._authorization_activities(bill))
        with self.assertRaises(UserError):
            bill.with_user(self.user_authorizer).action_authorize_bill()
        with self.assertRaises(UserError):
            bill.with_user(self.user_authorizer).action_authorize_and_confirm_bill()
        self._post_blocked(bill, self.env.user)
        self.assertEqual(bill.state, "draft")

    def test_always_block_wins_over_earlier_authorization(self):
        bill = self._create_bill(self.classification_sensitive, partner=self.partner_b)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        self.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Never pay partner B",
                "domain": str([("partner_id", "=", self.partner_b.id)]),
                "always_block": True,
            }
        )
        self._post_blocked(bill, self.user_other)
        self.assertEqual(bill.state, "draft")
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertFalse(bill.authorized_by_id)

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
                bill = self._create_bill(self.classification_sensitive, partner=self.partner_b)
                self.assertEqual(bill.matched_policy_ids, self.policy_sensitive | policy_partner)
                self.assertEqual(
                    bill.pending_authorizer_ids, self.user_authorizer | self.user_authorizer_2
                )
                bill.with_user(authorizer).action_authorize_bill()
                self.assertEqual(bill.authorization_state, "authorized")
                self.assertEqual(bill.authorized_by_id, authorizer)

    def test_editing_authorized_bill_resets_authorization(self):
        policy_partner = self.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Partner B bills",
                "domain": str([("partner_id", "=", self.partner_b.id)]),
                "authorized_user_ids": [Command.set([self.user_authorizer_2.id])],
            }
        )
        purchase_journal = self.company_data["default_journal_purchase"]
        other_journal = purchase_journal.copy(
            {"code": "BILL2", "default_account_id": purchase_journal.default_account_id.id}
        )
        edits = {
            "partner_id": lambda bill: {"partner_id": self.partner_b.id},
            "journal_id": lambda bill: {"journal_id": other_journal.id},
            "invoice_date": lambda bill: {"invoice_date": "2026-02-01"},
            "invoice_line_ids": lambda bill: {
                "invoice_line_ids": [Command.update(bill.invoice_line_ids.id, {"price_unit": 5000.0})]
            },
            "classification_id": lambda bill: {"classification_id": self.classification_two.id},
        }
        for fname, make_vals in edits.items():
            with self.subTest(field=fname):
                bill = self._create_bill(self.classification_sensitive)
                bill.with_user(self.user_authorizer).action_authorize_bill()
                bill.with_user(self.user_creator).write(make_vals(bill))
                self.assertEqual(bill.authorization_state, "to_authorize")
                self.assertFalse(bill.authorized_by_id)
                self.assertTrue(
                    any("Authorization reset" in (m or "") for m in bill.message_ids.mapped("body"))
                )
                if fname == "partner_id":
                    self.assertEqual(bill.matched_policy_ids, self.policy_sensitive | policy_partner)
                if fname == "classification_id":
                    self.assertEqual(bill.matched_policy_ids, self.policy_two)
                # The reset bill can no longer be confirmed by a non-authorizer.
                self._post_blocked(bill, self.user_other)
                self.assertEqual(bill.state, "draft")

    def test_editing_rejected_bill_resets_rejection(self):
        bill = self._create_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer)._reject_bill("Too expensive")
        self.assertEqual(bill.authorization_state, "rejected")
        bill.with_user(self.user_creator).write(
            {"invoice_line_ids": [Command.update(bill.invoice_line_ids.id, {"price_unit": 50.0})]}
        )
        self.assertEqual(bill.authorization_state, "to_authorize")

    def test_edit_resetting_to_unmatched_bill_becomes_not_required(self):
        bill = self._create_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        bill.with_user(self.user_creator).classification_id = False
        self.assertFalse(bill.matched_policy_ids)
        self.assertEqual(bill.authorization_state, "not_required")

    def test_authorization_survives_edit_to_non_sensitive_field(self):
        bill = self._create_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        bill.with_user(self.user_creator).ref = "SUPPLIER-REF-1"
        self.assertEqual(bill.authorization_state, "authorized")
        self.assertEqual(bill.authorized_by_id, self.user_authorizer)

    def test_reset_to_draft_requires_new_authorization(self):
        bill = self._create_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_and_confirm_bill()
        self.assertEqual(bill.state, "posted")

        bill.button_draft()

        self.assertEqual(bill.state, "draft")
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertFalse(bill.authorized_by_id)
        self.assertTrue(
            any("was reset to draft" in (m or "") for m in bill.message_ids.mapped("body"))
        )
        self._post_blocked(bill, self.user_other)
        self.assertEqual(bill.state, "draft")

    def test_unauthorize_only_while_draft(self):
        bill = self._create_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()

        # Any current pending authorizer can unauthorize, not only the one
        # who authorized it.
        self.policy_sensitive.authorized_user_ids = [Command.link(self.user_authorizer_2.id)]
        bill.with_user(self.user_authorizer_2).action_unauthorize_bill()
        self.assertEqual(bill.authorization_state, "to_authorize")
        self.assertFalse(bill.authorized_by_id)
        creator_activity = self._authorization_activities(bill).filtered(
            lambda a: a.user_id == self.user_creator
        )
        self.assertEqual(len(creator_activity), 1)

        bill.with_user(self.user_authorizer).action_authorize_and_confirm_bill()
        self.assertEqual(bill.state, "posted")
        with self.assertRaises(UserError):
            bill.with_user(self.user_authorizer).action_unauthorize_bill()

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
        self.assertFalse(invoice.matched_policy_ids)
        self.assertEqual(invoice.authorization_state, "not_required")
        invoice.with_user(self.user_creator).action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.authorization_state, "not_required")

    def test_vendor_refund_triggers_authorization(self):
        refund = self._create_bill(self.classification_sensitive, move_type="in_refund")
        self.assertEqual(refund.authorization_state, "to_authorize")
        self._post_blocked(refund, self.user_creator)
        self.assertEqual(refund.state, "draft")
        self.assertTrue(self._authorization_activities(refund))
        refund.with_user(self.user_authorizer).action_authorize_and_confirm_bill()
        self.assertEqual(refund.state, "posted")

    def test_non_authorizer_cannot_authorize_reject_or_unauthorize(self):
        bill = self._create_bill(self.classification_sensitive)
        with self.assertRaises(AccessError):
            bill.with_user(self.user_other).action_authorize_bill()
        with self.assertRaises(AccessError):
            bill.with_user(self.user_other).action_authorize_and_confirm_bill()
        with self.assertRaises(AccessError):
            bill.with_user(self.user_other).action_reject_bill()
        bill.with_user(self.user_authorizer).action_authorize_bill()
        with self.assertRaises(AccessError):
            bill.with_user(self.user_other).action_unauthorize_bill()

    def test_cannot_reauthorize_or_reject_once_authorized(self):
        bill = self._create_bill(self.classification_sensitive)
        bill.with_user(self.user_authorizer).action_authorize_bill()
        with self.assertRaises(UserError):
            bill.with_user(self.user_authorizer).action_authorize_bill()
        with self.assertRaises(UserError):
            bill.with_user(self.user_authorizer).action_reject_bill()

    def test_post_safety_net_blocks_validate_wizard(self):
        """The "Post entries" list action posts through the
        validate.account.move wizard, which calls _post() directly without
        going through action_post().
        """
        bill = self._create_bill(self.classification_sensitive)
        wizard = (
            self.env["validate.account.move"]
            .with_user(self.user_creator)
            .create({"move_ids": [Command.set(bill.ids)]})
        )
        with self.assertRaises(UserError):
            wizard.validate_move()
        self.assertEqual(bill.state, "draft")

        bill.with_user(self.user_authorizer).action_authorize_bill()
        wizard.with_user(self.user_other).validate_move()
        self.assertEqual(bill.state, "posted")

    def test_full_reversal_of_posted_bill_is_not_blocked(self):
        self.env["account.vendor.bill.authorization.policy"].create(
            {
                "name": "Catch-all",
                "domain": "[]",
                "authorized_user_ids": [Command.set([self.user_authorizer.id])],
            }
        )
        bill = self._create_bill()
        bill.with_user(self.user_authorizer).action_post()
        reversal = (
            self.env["account.move.reversal"]
            .with_user(self.user_creator)
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"journal_id": bill.journal_id.id, "reason": "Full refund"})
        )
        # "Modify" (full refund + new draft) is the reversal flow that posts
        # the credit note immediately (move_reverse_cancel).
        reversal.modify_moves()
        refund = bill.reversal_move_ids
        self.assertEqual(refund.state, "posted")
        self.assertEqual(refund.authorization_state, "not_required")

    def test_blocking_a_bill_commits_before_raising_outside_tests(self):
        """Without an explicit commit before the final raise, every write
        action_post() just made while blocking a bill (authorization_state,
        activities, chatter messages) would be rolled back by the RPC
        dispatcher in real usage. Confirm the commit is called, using a mock
        instead of a real commit against the shared per-test transaction.
        """
        bill = self._create_bill(self.classification_sensitive)
        with patch.object(odoo_module, "current_test", False), patch.object(
            self.env.cr, "commit"
        ) as mock_commit:
            with self.assertRaises(UserError):
                bill.with_user(self.user_creator).action_post()
            mock_commit.assert_called_once()

    def test_policy_condition_change_is_picked_up_on_post(self):
        """Editing a policy's domain does not recompute stored matches on
        existing drafts by itself; action_post() must evaluate the live
        configuration anyway.
        """
        bill = self._create_bill()
        self.assertEqual(bill.authorization_state, "not_required")
        self.policy_sensitive.domain = str([("partner_id", "=", self.partner_a.id)])
        self._post_blocked(bill, self.user_creator)
        self.assertEqual(bill.state, "draft")
        self.assertEqual(bill.matched_policy_ids, self.policy_sensitive)

    def test_amount_tier_policies(self):
        policy_model = self.env["account.vendor.bill.authorization.policy"]
        policy_low = policy_model.create(
            {
                "name": "Low",
                "domain": str([("amount_total", "<", 1000)]),
                "authorized_user_ids": [Command.set([self.user_authorizer.id])],
            }
        )
        policy_high = policy_model.create(
            {
                "name": "High",
                "domain": str([("amount_total", ">=", 1000)]),
                "authorized_user_ids": [Command.set([self.user_authorizer_2.id])],
            }
        )
        bill = self._create_bill(price=100.0)
        self.assertEqual(bill.matched_policy_ids, policy_low)
        bill.with_user(self.user_creator).write(
            {"invoice_line_ids": [Command.update(bill.invoice_line_ids.id, {"price_unit": 5000.0})]}
        )
        self.assertEqual(bill.matched_policy_ids, policy_high)
        self.assertEqual(bill.pending_authorizer_ids, self.user_authorizer_2)

    def test_search_filters(self):
        bill_pending = self._create_bill(self.classification_sensitive)
        bill_other_authorizer = self._create_bill(self.classification_two)
        bill_authorized = self._create_bill(self.classification_sensitive)
        bill_authorized.with_user(self.user_authorizer).action_authorize_bill()
        bill_authorized_by_other_creator = self._create_bill(
            self.classification_sensitive, user=self.user_manager
        )
        bill_authorized_by_other_creator.with_user(self.user_authorizer).action_authorize_bill()
        bill_rejected = self._create_bill(self.classification_sensitive)
        bill_rejected.with_user(self.user_authorizer)._reject_bill("No")
        bill_confirmed = self._create_bill(self.classification_sensitive)
        bill_confirmed.with_user(self.user_authorizer).action_authorize_and_confirm_bill()
        bill_no_authorizers = self._create_bill(self.classification_blocked)
        bills = (
            bill_pending | bill_other_authorizer | bill_authorized
            | bill_authorized_by_other_creator | bill_rejected | bill_confirmed
            | bill_no_authorizers
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
            search("authorization_to_authorize_by_me", self.user_authorizer),
            bill_pending | bill_other_authorizer,
        )
        self.assertEqual(
            search("authorization_authorized_unconfirmed_by_me", self.user_creator),
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

    def test_new_policy_defaults(self):
        policy = self.env["account.vendor.bill.authorization.policy"].create({"name": "Defaults"})
        self.assertEqual(policy.company_id, self.env.company)
        self.assertEqual(
            safe_eval(policy.domain),
            [("move_type", "in", ["in_invoice", "in_refund"]), ("state", "=", "draft")],
        )
