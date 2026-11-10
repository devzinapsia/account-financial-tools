"""Integration with the ingadhoc Argentinian stack our clients use: l10n_ar_tax
(withholding certificates attached to payment orders) and, when installed,
l10n_ar_payment_bundle. Skipped in databases without those modules."""

from unittest import SkipTest

from odoo import Command, fields
from odoo.modules.registry import Registry
from odoo.tests import tagged
from odoo.tests.common import get_db_name

from odoo.addons.account_payment_email_invoices.wizard.mail_compose_message import PAYMENT_INVOICE_MARKER
# Import the module, not the class: a test class imported into this module
# would be collected and run again as one of this module's tests.
from odoo.addons.l10n_ar_withholding.tests import test_withholding_ar_ri


@tagged("post_install", "-at_install")
class TestPaymentEmailInvoicesL10nArTax(test_withholding_ar_ri.TestArWithholdingArRi):

    @classmethod
    def setUpClass(cls):
        if "l10n_ar_tax" not in Registry(get_db_name())._init_modules:
            raise SkipTest("l10n_ar_tax is not installed")
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, lang="en_US"))
        cls.today = fields.Date.today()
        cls.bank_journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company_ri.id), ("type", "=", "bank")], limit=1
        )
        cls.receipt_template = cls.env.ref("account.mail_template_data_payment_receipt")
        cls.res_partner_adhoc.email = "adhoc@example.com"
        cls.number = 714300

    def _bill(self, move_type="in_invoice", amount=100000):
        type(self).number += 1
        bill = self.env["account.move"].create(
            {
                "partner_id": self.res_partner_adhoc.id,
                "move_type": move_type,
                "company_id": self.company_ri.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [Command.set(self.tax_21.ids)],
                        }
                    )
                ],
                "invoice_date": self.today,
                "l10n_latam_document_number": "1-%s" % self.number,
            }
        )
        bill.action_post()
        attachment = self.env["ir.attachment"].create(
            {
                "name": "vendor.pdf",
                "raw": b"%PDF-1.4 vendor document",
                "mimetype": "application/pdf",
                "res_model": "account.move",
                "res_id": bill.id,
            }
        )
        bill.message_main_attachment_id = attachment
        return bill

    def _payment_with_withholdings(self, bills):
        action_context = bills.action_register_payment()["context"]
        payment = (
            self.env["account.payment"]
            .with_context(**action_context)
            .create({"journal_id": self.bank_journal.id, "date": self.today})
        )
        payment.l10n_ar_withholding_line_ids = [
            Command.create({"tax_id": self.tax_wth_test_1.id, "base_amount": 100000.0, "amount": 3000.0}),
            Command.create({"tax_id": self.tax_wth_test_2.id, "base_amount": 121000.0, "amount": 2500.0}),
        ]
        payment.action_post()
        return payment

    def _composer(self, payments, mode="comment"):
        return (
            self.env["mail.compose.message"]
            .with_context(
                default_model="account.payment",
                default_res_ids=payments.ids,
                default_composition_mode=mode,
                default_template_id=self.receipt_template.id,
            )
            .create({})
        )

    def test_withholdings_unchanged_and_first(self):
        """The receipt and the withholding certificates are attached exactly as
        without this module, and come first; the bills come last."""
        bill = self._bill()
        payment = self._payment_with_withholdings(bill)
        certificates_name = payment._l10n_ar_withholding_certificates_filename()

        self.company_ri.attach_invoices_on_payment_order = False
        original = self._composer(payment).attachment_ids.sorted("id")
        self.assertIn(certificates_name, original.mapped("name"))
        self.assertFalse(original.filtered(lambda a: a.description == PAYMENT_INVOICE_MARKER))

        self.company_ri.attach_invoices_on_payment_order = True
        composer = self._composer(payment)
        ours = composer.attachment_ids.filtered(lambda a: a.description == PAYMENT_INVOICE_MARKER)
        others = (composer.attachment_ids - ours).sorted("id")
        self.assertEqual(others.mapped("name"), original.mapped("name"))
        self.assertEqual(others.mapped("raw"), original.mapped("raw"))

        message = composer._action_send_mail()[1]
        names = message.attachment_ids.sorted("id").mapped("name")
        self.assertEqual(names, original.mapped("name") + [bill._get_payment_email_attachment_name()])

    def test_mass_sending(self):
        """Mass sending: receipt, certificates, then the bills of each payment."""
        self.company_ri.attach_invoices_on_payment_order = True
        bill_1, bill_2 = self._bill(), self._bill()
        payment_1 = self._payment_with_withholdings(bill_1)
        payment_2 = self._payment_with_withholdings(bill_2)
        mails = self._composer(payment_1 | payment_2, mode="mass_mail")._action_send_mail()[0]
        for payment, bill in ((payment_1, bill_1), (payment_2, bill_2)):
            mail = mails.filtered(lambda m, p=payment: m.res_id == p.id)
            names = mail.attachment_ids.sorted("id").mapped("name")
            self.assertEqual(names[-1], bill._get_payment_email_attachment_name())
            self.assertIn(payment._l10n_ar_withholding_certificates_filename(), names[:-1])

    def test_bundle_with_credit_note(self):
        """Payment bundle (l10n_ar_payment_bundle): the main payment, which has
        no journal entry, attaches the bill and the credit note settled by its
        linked payments."""
        if "l10n_ar_payment_bundle" not in self.env.registry._init_modules:
            self.skipTest("l10n_ar_payment_bundle is not installed")
        company = self.company_ri
        company.write({"use_payment_pro": True, "attach_invoices_on_payment_order": True})
        bill = self._bill(amount=80000)
        credit_note = self._bill(move_type="in_refund", amount=10000)
        bundle_journal = self.env["account.journal"].browse(company._get_bundle_journal("outbound"))
        bundle_method = bundle_journal.outbound_payment_method_line_ids.filtered(
            lambda line: line.payment_method_id.code == "payment_bundle"
        )[:1]
        debt = (bill | credit_note).line_ids.filtered(lambda line: line.account_type == "liability_payable")
        main = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.res_partner_adhoc.id,
                "journal_id": bundle_journal.id,
                "payment_method_line_id": bundle_method.id,
                "amount": 0,
                "to_pay_move_line_ids": [Command.set(debt.ids)],
            }
        )
        manual = self.bank_journal.outbound_payment_method_line_ids.filtered(
            lambda line: line.payment_method_id.code == "manual"
        )[:1]
        self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.res_partner_adhoc.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": manual.id,
                "amount": 50000,
                "main_payment_id": main.id,
            }
        )
        main.action_post()
        self.assertFalse(main.move_id)
        composer = self._composer(main)
        ours = composer.attachment_ids.filtered(lambda a: a.description == PAYMENT_INVOICE_MARKER)
        self.assertEqual(
            sorted(ours.mapped("name")),
            sorted(move._get_payment_email_attachment_name() for move in bill | credit_note),
        )
