from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account_payment_email_invoices.wizard.mail_compose_message import PAYMENT_INVOICE_MARKER


@tagged("post_install", "-at_install")
class TestAccountPaymentEmailInvoicesPaymentPro(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.env.user.lang = "en_US"
        cls.company = cls.company_data["company"]
        cls.company.write(
            {
                "use_payment_pro": True,
                "attach_invoices_on_payment_order": True,
                "attach_invoices_on_receipt": True,
            }
        )
        cls.partner_a.email = "partner_a@example.com"
        cls.template = cls.env.ref("account.mail_template_data_payment_receipt")
        cls.bank_journal = cls.company_data["default_journal_bank"]

    def _move(self, amount, move_type="in_invoice"):
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
                "date": "2026-01-01",
                "invoice_line_ids": [Command.create({"name": "line", "quantity": 1, "price_unit": amount, "tax_ids": []})],
            }
        )
        move.action_post()
        if move.is_purchase_document():
            attachment = self.env["ir.attachment"].create(
                {
                    "name": "vendor-%s.pdf" % move.id,
                    "raw": b"%PDF-1.4 vendor document",
                    "mimetype": "application/pdf",
                    "res_model": "account.move",
                    "res_id": move.id,
                }
            )
            move.message_main_attachment_id = attachment
        return move

    def _payment(self, amount, moves, payment_type="outbound"):
        account_type = "liability_payable" if payment_type == "outbound" else "asset_receivable"
        lines = moves.line_ids.filtered(lambda line: line.account_type == account_type and not line.reconciled)
        method_lines = (
            self.bank_journal.outbound_payment_method_line_ids
            if payment_type == "outbound"
            else self.bank_journal.inbound_payment_method_line_ids
        )
        payment = self.env["account.payment"].create(
            {
                "payment_type": payment_type,
                "partner_type": "supplier" if payment_type == "outbound" else "customer",
                "partner_id": self.partner_a.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": method_lines[:1].id,
                "amount": amount,
                "date": "2026-01-02",
                "to_pay_move_line_ids": [Command.set(lines.ids)],
            }
        )
        payment.action_post()
        return payment

    def _attached(self, payment):
        composer = (
            self.env["mail.compose.message"]
            .with_context(
                default_model="account.payment",
                default_res_ids=payment.ids,
                default_composition_mode="comment",
                default_template_id=self.template.id,
            )
            .create({})
        )
        return sorted(composer.attachment_ids.filtered(lambda a: a.description == PAYMENT_INVOICE_MARKER).mapped("name"))

    @staticmethod
    def _names(moves):
        return sorted(move._get_payment_email_attachment_name() for move in moves)

    def test_credit_note_in_payment_order(self):
        """account_payment_pro reconciles the credit note with the bill, not
        with the payment: it is attached anyway."""
        bill_1, bill_2 = self._move(1000), self._move(500)
        credit_note = self._move(200, move_type="in_refund")
        payment = self._payment(1300, bill_1 | bill_2 | credit_note)
        self.assertNotIn(credit_note, payment.reconciled_bill_ids, "Precondition: not reconciled with the payment.")
        self.assertEqual(self._attached(payment), self._names(bill_1 | bill_2 | credit_note))

    def test_credit_note_in_receipt(self):
        invoice = self._move(1000, move_type="out_invoice")
        credit_note = self._move(300, move_type="out_refund")
        payment = self._payment(700, invoice | credit_note, payment_type="inbound")
        self.assertEqual(self._attached(payment), self._names(invoice | credit_note))

    def test_partial_payment(self):
        """Debts selected but not reached by a partial payment are not attached;
        an invoice paid by two payments is attached to both."""
        bill_1, bill_2 = self._move(1000), self._move(1000)
        payment_1 = self._payment(300, bill_1 | bill_2)
        self.assertEqual(self._attached(payment_1), self._names(bill_1))
        payment_2 = self._payment(1700, bill_1 | bill_2)
        self.assertEqual(self._attached(payment_2), self._names(bill_1 | bill_2))
        self.assertEqual(self._attached(payment_1), self._names(bill_1))

    def test_credit_note_applied_before_not_attached(self):
        """A credit note reconciled with the bill before the payment did not
        intervene in it."""
        bill = self._move(1000)
        credit_note = self._move(200, move_type="in_refund")
        (bill | credit_note).line_ids.filtered(lambda line: line.account_type == "liability_payable").reconcile()
        partials = credit_note.line_ids.matched_credit_ids | credit_note.line_ids.matched_debit_ids
        # All the test runs in one transaction: make the earlier operation look earlier.
        self.env.cr.execute(
            "UPDATE account_partial_reconcile SET create_date = create_date - interval '1 day' WHERE id IN %s",
            (tuple(partials.ids),),
        )
        partials.invalidate_recordset(["create_date"])
        payment = self._payment(800, bill)
        self.assertEqual(self._attached(payment), self._names(bill))

    def test_bundle_payments(self):
        """A payment bundle: the main payment has no journal entry, its linked
        payments (returned by _get_mached_payment) settle the documents."""
        bill = self._move(1000)
        credit_note = self._move(100, move_type="in_refund")
        linked = self._payment(900, bill | credit_note)
        main = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "journal_id": self.bank_journal.id,
                "amount": 0,
                "to_pay_move_line_ids": [Command.clear()],
            }
        )
        self.assertFalse(self._attached(main))
        Payment = type(self.env["account.payment"])
        original = Payment._get_mached_payment

        def _get_mached_payment(payment):
            ids = original(payment)
            return ids + linked.ids if payment == main else ids

        with patch.object(Payment, "_get_mached_payment", _get_mached_payment):
            self.assertEqual(self._attached(main), self._names(bill | credit_note))
