import re

from odoo import Command, fields
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestL10nArTaxReceiptWithholdingNumber(TestArCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_ri
        cls.company.use_payment_pro = True
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.bank_journal = cls.env["account.journal"].create(
            {
                "name": "Bank withholding number test",
                "type": "bank",
                "code": "BWNT",
                "company_id": cls.company.id,
            }
        )
        wth_account = cls.env["account.account"].create(
            {
                "name": "Withholdings test",
                "code": "WNTWTH",
                "account_type": "liability_current",
                "company_ids": [Command.set(cls.company.ids)],
            }
        )
        repartition = [
            Command.create({"factor_percent": 100, "repartition_type": "base"}),
            Command.create({"factor_percent": 100, "repartition_type": "tax", "account_id": wth_account.id}),
        ]
        cls.tax_iibb, cls.tax_earnings, cls.tax_suss = cls.env["account.tax"].create(
            [
                {
                    "name": name,
                    "amount": 1.0,
                    "amount_type": "percent",
                    "type_tax_use": "none",
                    "company_id": cls.company.id,
                    "l10n_ar_tax_type": tax_type,
                    "l10n_ar_withholding_payment_type": "supplier",
                    "invoice_repartition_line_ids": repartition,
                    "refund_repartition_line_ids": repartition,
                }
                for name, tax_type in [
                    ("Ret IIBB MZA", "iibb_untaxed"),
                    ("Ret Ganancias", "earnings"),
                    ("Ret SUSS", False),
                ]
            ]
        )

    def _create_payment(self, withholdings):
        """Draft supplier payment with the given (tax, amount, number) withholding lines."""
        payment = self.env["account.payment"].create(
            {
                "journal_id": self.bank_journal.id,
                "partner_id": self.res_partner_adhoc.id,
                "partner_type": "supplier",
                "payment_type": "outbound",
                "date": fields.Date.today(),
                "amount": 10_000,
            }
        )
        self.env["l10n_ar.payment.withholding"].create(
            [
                {"payment_id": payment.id, "tax_id": tax.id, "amount": amount, "name": number}
                for tax, amount, number in withholdings
            ]
        )
        return payment

    def _render_text(self, payment):
        """Receipt HTML reduced to plain text with collapsed whitespace."""
        html = self.env["ir.actions.report"]._render_qweb_html("account.report_payment_receipt", payment.ids)[0]
        text = re.sub(r"<[^>]+>", " ", html.decode())
        return re.sub(r"\s+", " ", text)

    def test_each_withholding_shows_its_own_number(self):
        """Several withholdings: every row carries its own certificate number."""
        payment = self._create_payment(
            [
                (self.tax_iibb, 300, "0001-00000123"),
                (self.tax_earnings, 700, "0001-00000456"),
                (self.tax_suss, 100, "0001-00000789"),
            ]
        )
        text = self._render_text(payment)
        self.assertIn("Ret IIBB MZA - Cert. No. 0001-00000123", text)
        self.assertIn("- Cert. No. 0001-00000456", text)
        self.assertIn("Ret SUSS - Cert. No. 0001-00000789", text)
        self.assertEqual(text.count("Cert. No."), 3)

    def test_no_number_no_separator(self):
        """Lines without a number, or with the "/" placeholder, show the tax label only."""
        payment = self._create_payment(
            [
                (self.tax_iibb, 300, False),
                (self.tax_suss, 100, "/"),
            ]
        )
        text = self._render_text(payment)
        self.assertIn("Ret IIBB MZA", text)
        self.assertIn("Ret SUSS", text)
        self.assertNotIn("Cert. No.", text)

    def test_zero_amount_line_not_printed(self):
        """Zero-amount lines stay filtered out by l10n_ar_tax, number included."""
        payment = self._create_payment(
            [
                (self.tax_iibb, 300, "0001-00000123"),
                (self.tax_suss, 0, "0001-00000999"),
            ]
        )
        text = self._render_text(payment)
        self.assertIn("Cert. No. 0001-00000123", text)
        self.assertNotIn("0001-00000999", text)
