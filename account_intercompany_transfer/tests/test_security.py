from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from ..models.account_intercompany_transfer import internal_write
from .common import IntercompanyTransferCommon


@tagged("post_install", "-at_install")
class TestIntercompanyTransferSecurity(IntercompanyTransferCommon):
    def test_user_without_group(self):
        with self.assertRaises(AccessError):
            self._as_user("account.intercompany.transfer.wizard", self.user_no_group).create(
                {
                    "origin_journal_id": self.cash_a.id,
                    "destination_company_id": self.company_b.id,
                    "destination_journal_id": self.cash_b.id,
                    "amount": 10.0,
                }
            )
        with self.assertRaisesRegex(AccessError, "not allowed to make intercompany transfers"):
            self._transfer(user=self.user_no_group)
        transfer = self._transfer()
        with self.assertRaises(AccessError):
            transfer.with_user(self.user_no_group).read(["name"])
        with self.assertRaises(AccessError):
            self._as_user("account.intercompany.transfer", self.user_no_group).search([])

    def test_user_without_destination_company(self):
        with self.assertRaisesRegex(AccessError, "not allowed to use the selected journals"):
            self._transfer(user=self.user_only_a)

    def test_record_rules(self):
        transfer = self._transfer()
        Transfer = self.env["account.intercompany.transfer"]
        user_only_b = self._create_user("ict_only_b", self.company_b, self.group_transfer | self.group_invoice)
        user_only_c = self._create_user("ict_only_c", self.company_c, self.group_transfer | self.group_invoice)
        self.assertIn(transfer, Transfer.with_user(self.user_only_a).search([]), "Origin company allowed.")
        self.assertIn(transfer, Transfer.with_user(user_only_b).search([]), "Destination company allowed.")
        self.assertNotIn(transfer, Transfer.with_user(user_only_c).search([]))
        with self.assertRaises(AccessError):
            transfer.with_user(user_only_c).read(["name"])
        # Visible with only one of its companies ticked.
        self.assertIn(transfer, self._as_user("account.intercompany.transfer", ticked=self.company_a).search([]))

    def test_no_bypass_on_the_document(self):
        transfer = self._transfer().with_user(self.user_transfer)
        Transfer = self._as_user("account.intercompany.transfer")
        with self.assertRaisesRegex(UserError, "only be created from the transfer wizard"):
            Transfer.create(
                {
                    "company_id": self.company_a.id,
                    "destination_company_id": self.company_b.id,
                    "origin_journal_id": self.cash_a.id,
                    "destination_journal_id": self.cash_b.id,
                    "amount": 1.0,
                    "currency_id": self.currency.id,
                    "date": self.today,
                }
            )
        for vals in (
            {"amount": 1.0},
            {"destination_journal_id": self.bank_b.id},
            {"state": "cancelled"},
            {"origin_payment_id": False},
        ):
            with self.subTest(vals=vals), self.assertRaisesRegex(UserError, "Only the memo"):
                transfer.write(vals)
        with self.assertRaisesRegex(UserError, "can't be deleted"):
            transfer.unlink()
        transfer.memo = "New memo"
        self.assertEqual(transfer.memo, "New memo")

    def test_payments_locked(self):
        transfer = self._transfer()
        payment = transfer.origin_payment_id.with_user(self.user_transfer).with_context(
            allowed_company_ids=self.company_a.ids
        )
        for vals in ({"amount": 1.0}, {"memo": "Changed"}, {"date": "2020-01-01"}, {"partner_id": False}):
            with self.subTest(vals=vals), self.assertRaisesRegex(UserError, "Cancel the transfer instead"):
                payment.write(vals)
        for method in ("action_draft", "action_cancel", "action_reject"):
            with self.subTest(method=method), self.assertRaisesRegex(UserError, "Cancel the transfer instead"):
                getattr(payment, method)()
        with self.assertRaisesRegex(UserError, "can't be deleted"):
            payment.unlink()
        with self.assertRaisesRegex(UserError, "Cancel the transfer instead"):
            payment.move_id.button_draft()
        with self.assertRaisesRegex(UserError, "Cancel the transfer instead"):
            payment.move_id._reverse_moves(cancel=True)

    def test_payment_link_by_hand(self):
        transfer = self._transfer()
        Payment = self._as_user("account.payment")
        values = {
            "payment_type": "outbound",
            "partner_type": "customer",
            "journal_id": self.cash_a.id,
            "amount": 1.0,
        }
        with self.assertRaisesRegex(UserError, "only be created by the transfer wizard"):
            Payment.create({**values, "intercompany_transfer_id": transfer.id})
        payment = Payment.create(values)
        with self.assertRaisesRegex(UserError, "can't be linked to an intercompany transfer by hand"):
            payment.write({"intercompany_transfer_id": transfer.id})

    def test_internal_transfer_payment_cannot_be_linked(self):
        """Even from inside the module's own flows, a payment carrying an
        internal transfer marker is rejected.
        """
        transfer = self._transfer()
        paired = self.env["account.payment"].create(
            {"payment_type": "inbound", "partner_type": "customer", "journal_id": self.bank_a.id, "amount": 1.0}
        )
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "customer",
                "journal_id": self.cash_a.id,
                "amount": 1.0,
                "paired_internal_transfer_payment_id": paired.id,
            }
        )
        with internal_write(), self.assertRaisesRegex(ValidationError, "is an internal transfer"):
            payment.write({"intercompany_transfer_id": transfer.id})
        with self.assertRaisesRegex(UserError, "can't be turned into an internal transfer"):
            transfer.origin_payment_id.write({"paired_internal_transfer_payment_id": paired.id})

    def test_open_payments(self):
        transfer = self._transfer().with_user(self.user_transfer).with_context(
            allowed_company_ids=self.company_a.ids
        )
        action = transfer.action_open_origin_payment()
        self.assertEqual(action["res_id"], transfer.sudo().origin_payment_id.id)
        with self.assertRaisesRegex(UserError, "Select that company in the company switcher"):
            transfer.action_open_destination_payment()
        transfer = transfer.with_context(allowed_company_ids=(self.company_a | self.company_b).ids)
        self.assertEqual(transfer.action_open_destination_payment()["res_id"], transfer.destination_payment_id.id)

    def test_group_is_standalone(self):
        self.assertFalse(self.group_transfer.implied_ids)
        self.assertFalse(self.env["res.groups"].search([("implied_ids", "in", self.group_transfer.ids)]))
        self.assertFalse(self.env.ref("base.user_admin").has_group(
            "account_intercompany_transfer.group_intercompany_transfer_user"
        ))
        self.user_no_group.group_ids = [Command.link(self.env.ref("account.group_account_manager").id)]
        self.assertFalse(self.user_no_group.has_group(
            "account_intercompany_transfer.group_intercompany_transfer_user"
        ))
