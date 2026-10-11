from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAccountPaymentReviewPaymentPro(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.company = cls.env.company
        cls.company.use_payment_pro = True
        cls.company.write(
            {
                "payment_review_enabled": True,
                "payment_review_min_amount": 1000.0,
                "payment_review_exempt_domain": "[]",
            }
        )
        cls.bank_journal = cls.env["account.journal"].create(
            {"name": "Review Pro Bank", "type": "bank", "code": "RVPB", "company_id": cls.company.id}
        )
        cls.vendor = cls.env["res.partner"].create({"name": "Distribuidora Río Sur S.R.L."})
        cls.reviewer = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Pro Reviewer",
                    "login": "pro_reviewer",
                    "lang": "en_US",
                    "company_id": cls.company.id,
                    "company_ids": [Command.set(cls.company.ids)],
                    "group_ids": [Command.set(cls.env.ref("account_payment_review.group_payment_reviewer").ids)],
                }
            )
        )

    def _create_payment(self, amount):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.vendor.id,
                "journal_id": self.bank_journal.id,
                "amount": amount,
            }
        )
        payment.action_post()
        return payment

    def test_min_amount_uses_payment_total(self):
        small = self._create_payment(500.0)
        big = self._create_payment(1500.0)
        self.assertTrue(big.use_payment_pro)
        self.assertEqual(big._review_amount(), abs(big.payment_total))
        self.assertEqual(small.review_state, "not_required")
        self.assertEqual(big.review_state, "pending")

    def test_review_wizard_shows_payment_total(self):
        payment = self._create_payment(1500.0)
        wizard = (
            self.env["account.payment.review.wizard"]
            .with_user(self.reviewer)
            .with_context(active_model="account.payment", active_ids=payment.ids)
            .create({})
        )
        self.assertEqual(wizard.line_ids.payment_total, payment.payment_total)
        wizard.action_confirm()
        self.assertEqual(payment.review_state, "reviewed")
