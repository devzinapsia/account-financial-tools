from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentAuthorizationPaymentPro(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.classification = cls.env["account.move.classification"].create(
            {"name": "PproClass"}
        )
        cls.user_authorizer = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Ppro Authorizer",
                    "login": "ppro_authorizer",
                    "email": "ppro_authorizer@test.example.com",
                    "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
                }
            )
        )
        cls.scheme = cls.env["account.payment.authorization.scheme"].create(
            {
                "name": "Ppro scheme",
                "domain": str([("invoice_ids.classification_id", "=", cls.classification.id)]),
                "authorized_user_ids": [Command.set([cls.user_authorizer.id])],
            }
        )

    def _create_posted_bill(self, price=300.0):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
                "classification_id": self.classification.id,
                "invoice_line_ids": [
                    Command.create({"name": "x", "quantity": 1, "price_unit": price})
                ],
            }
        )
        bill.action_post()
        return bill

    def _create_ppro_draft_payment(self, bill):
        """Mimic account_payment_pro's own flow: the payment is created
        directly and the debt lines to settle are assigned to
        `to_pay_move_line_ids`, without ever going through
        account.payment.register.
        """
        payable_line = bill.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        )
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "amount": abs(sum(payable_line.mapped("amount_residual"))),
                "journal_id": self.company_data["default_journal_bank"].id,
                "payment_method_line_id": self.outbound_payment_method_line.id,
            }
        )
        payment.to_pay_move_line_ids = [Command.set(payable_line.ids)]
        return payment

    def _action_post_expect_blocked(self, payment):
        """Call action_post() expecting it to raise UserError, without using
        `self.assertRaises()`: Odoo's test `assertRaises` wraps the call in
        a cursor savepoint that gets rolled back once the expected
        exception is caught, which would also erase every change
        action_post() made before raising (authorization_state, the
        invoice_ids sync, the created activity) -- exactly what we need to
        inspect afterwards.
        """
        try:
            payment.action_post()
            self.fail("Expected a UserError blocking the payment.")
        except UserError:
            pass

    def test_payment_pro_draft_syncs_invoice_ids_and_matches_scheme(self):
        bill = self._create_posted_bill()
        payment = self._create_ppro_draft_payment(bill)

        # Reading matched_scheme_ids (rather than invoice_ids directly) is
        # what actually triggers the payment_pro -> invoice_ids sync, since
        # it's a side effect of that field's compute, not of invoice_ids
        # itself -- matching how the web client naturally exercises it by
        # reading every field shown on the Authorization tab after any
        # change to the draft.
        self.assertIn(self.scheme, payment.matched_scheme_ids)
        self.assertEqual(payment.invoice_ids, bill)
        self.assertEqual(payment.pending_authorizer_ids, self.user_authorizer)

    def test_payment_pro_invoice_ids_tracks_current_selection_not_history(self):
        """Switching which bill `to_pay_move_line_ids` points to (or
        clearing it) must update `invoice_ids` to match exactly -- not
        accumulate every bill ever selected. A stale leftover here would
        also leak into l10n_ar_payment_bundle.button_open_invoices() and
        core's reconciled_bill_ids stat button count, both of which read
        `invoice_ids` directly.
        """
        bill_a = self._create_posted_bill(price=100.0)
        bill_b = self._create_posted_bill(price=200.0)
        payment = self._create_ppro_draft_payment(bill_a)
        # Reading matched_scheme_ids (not invoice_ids directly) is what
        # triggers the sync -- see test_payment_pro_draft_syncs_invoice_ids_
        # and_matches_scheme for why.
        payment.matched_scheme_ids
        self.assertEqual(payment.invoice_ids, bill_a)

        payable_line_b = bill_b.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        )
        payment.to_pay_move_line_ids = [Command.set(payable_line_b.ids)]
        payment.matched_scheme_ids
        self.assertEqual(payment.invoice_ids, bill_b)
        self.assertNotIn(bill_a, payment.invoice_ids)

        payment.to_pay_move_line_ids = [Command.clear()]
        payment.matched_scheme_ids
        self.assertFalse(payment.invoice_ids)

    def test_payment_pro_flow_blocks_unauthorized_confirmation(self):
        bill = self._create_posted_bill()
        payment = self._create_ppro_draft_payment(bill)

        self._action_post_expect_blocked(payment)

        self.assertEqual(payment.authorization_state, "to_authorize")
        self.assertEqual(payment.state, "draft")
        activity = payment.activity_ids.filtered(lambda a: a.user_id == self.user_authorizer)
        self.assertTrue(activity)

    def test_payment_pro_flow_authorizer_can_confirm(self):
        bill = self._create_posted_bill()
        payment = self._create_ppro_draft_payment(bill)

        payment.with_user(self.user_authorizer).action_post()

        self.assertEqual(payment.authorization_state, "authorized")
        self.assertEqual(payment.authorized_by_id, self.user_authorizer)
        self.assertNotEqual(payment.state, "draft")

    def test_payment_pro_authorizer_authorizes_untouched_draft(self):
        """The real-world reported scenario: account_payment_pro drafts the
        payment directly (to_pay_move_line_ids), and nobody has attempted
        to confirm it yet, so authorization_state is still its default
        "not_required". The authorizer must still be able to click
        Authorize straight away, without anyone first attempting (and
        being blocked from) confirming it.
        """
        bill = self._create_posted_bill()
        payment = self._create_ppro_draft_payment(bill)
        self.assertEqual(payment.authorization_state, "not_required")
        self.assertEqual(payment.pending_authorizer_ids, self.user_authorizer)

        payment.with_user(self.user_authorizer).action_authorize_payment()

        self.assertEqual(payment.authorization_state, "authorized")
        self.assertEqual(payment.authorized_by_id, self.user_authorizer)
        self.assertEqual(payment.state, "draft")

    def test_payment_pro_flow_non_authorizer_cannot_approve(self):
        bill = self._create_posted_bill()
        payment = self._create_ppro_draft_payment(bill)

        self._action_post_expect_blocked(payment)

        with self.assertRaises(AccessError):
            payment.action_authorize_payment()
