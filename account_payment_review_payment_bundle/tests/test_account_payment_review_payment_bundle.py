from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAccountPaymentReviewPaymentBundle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.company = cls.env.company
        cls.company.use_payment_pro = True
        cls.company.write(
            {
                "payment_review_enabled": True,
                "payment_review_min_amount": 10000.0,
                "payment_review_exempt_domain": "[]",
            }
        )
        # Same bundle setup as l10n_ar_payment_bundle's own tests.
        bundle_journal = cls.env["account.journal"].browse(cls.company._get_bundle_journal("outbound"))
        bundle_method = cls.env["account.payment.method"].search([("code", "=", "payment_bundle")], limit=1)
        cls.bundle_journal = bundle_journal
        cls.bundle_method_line = cls.env["account.payment.method.line"].search(
            [
                ("journal_id", "=", bundle_journal.id),
                ("payment_method_id", "=", bundle_method.id),
                ("payment_type", "=", "outbound"),
            ],
            limit=1,
        )
        cls.cash_journal = cls.env["account.journal"].create(
            {"name": "Review Bundle Cash", "type": "cash", "code": "RVBC", "company_id": cls.company.id}
        )
        cls.bank_journal = cls.env["account.journal"].create(
            {"name": "Review Bundle Bank", "type": "bank", "code": "RVBB", "company_id": cls.company.id}
        )
        if "store_id" in cls.env["account.journal"]._fields:
            purchase_journal = cls.env["account.journal"].search(
                [("company_id", "=", cls.company.id), ("type", "=", "purchase")], limit=1
            )
            (cls.bundle_journal | cls.cash_journal | cls.bank_journal).store_id = purchase_journal.store_id
        cls.vendor = cls.env["res.partner"].create({"name": "Distribuidora Río Sur S.R.L."})
        users = cls.env["res.users"].with_context(no_reset_password=True)

        def create_user(login, group_xmlid):
            return users.create(
                {
                    "name": login.replace("_", " ").title(),
                    "login": login,
                    "lang": "en_US",
                    "company_id": cls.company.id,
                    "company_ids": [Command.set(cls.company.ids)],
                    "group_ids": [Command.set(cls.env.ref(group_xmlid).ids)],
                }
            )

        cls.issuer = create_user("bundle_issuer", "account.group_account_manager")
        cls.reviewer = create_user("bundle_reviewer", "account_payment_review.group_payment_reviewer")

    def _manual_line(self, journal):
        return journal.outbound_payment_method_line_ids.filtered(lambda line: line.payment_method_id.code == "manual")

    def _create_bundle(self, cash_amount, bank_amount):
        Payment = self.env["account.payment"].with_user(self.issuer)
        main = Payment.create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.vendor.id,
                "journal_id": self.bundle_journal.id,
                "payment_method_line_id": self.bundle_method_line.id,
                "amount": 0,
            }
        )
        for journal, amount in ((self.cash_journal, cash_amount), (self.bank_journal, bank_amount)):
            Payment.create(
                {
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                    "partner_id": self.vendor.id,
                    "journal_id": journal.id,
                    "payment_method_line_id": self._manual_line(journal).id,
                    "amount": amount,
                    "main_payment_id": main.id,
                }
            )
        main.action_post()
        return main.with_user(self.env.user)

    def test_only_main_payment_is_reviewable(self):
        main = self._create_bundle(20000.0, 30000.0)
        linked = main.link_payment_ids
        self.assertTrue(main.is_main_payment)
        self.assertEqual(len(linked), 2)
        self.assertTrue(all(p.state in ("in_process", "paid") for p in main | linked))
        self.assertTrue(main.review_is_reviewable)
        self.assertFalse(any(linked.mapped("review_is_reviewable")))
        self.assertFalse(any(linked.mapped("review_state")), "Linked payments stay out of the circuit.")
        reviewable = self.env["account.payment"].search([("review_is_reviewable", "=", True)])
        self.assertIn(main, reviewable)
        self.assertFalse(linked & reviewable)
        with self.assertRaises(UserError):
            linked[:1].with_user(self.reviewer)._review_set_result("reviewed")

    def test_main_payment_amount_is_the_bundle_total(self):
        # The main payment's own amount is 0: without the bundle total it
        # would always fall below the minimum amount.
        big = self._create_bundle(20000.0, 30000.0)
        small = self._create_bundle(2000.0, 3000.0)
        self.assertEqual(big.amount, 0)
        self.assertEqual(big.review_state, "pending")
        self.assertEqual(small.review_state, "not_required")

    def test_review_main_payment(self):
        main = self._create_bundle(20000.0, 30000.0)
        wizard = (
            self.env["account.payment.review.wizard"]
            .with_user(self.reviewer)
            .with_context(active_model="account.payment", active_ids=main.ids)
            .create({})
        )
        self.assertEqual(wizard.line_ids.payment_total, 50000.0)
        wizard.write({"result": "observed", "comment": "Why split it?"})
        wizard.action_confirm()
        self.assertEqual(main.review_state, "observed")
        self.assertEqual(main.review_issuer_id, self.issuer)
        self.assertEqual(main.activity_ids.user_id, self.issuer)
