from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.models.account_payment import AccountPayment

from .common import IntercompanyTransferCommon


@tagged("post_install", "-at_install")
class TestIntercompanyTransferCancel(IntercompanyTransferCommon):
    def _cancel(self, transfer, user=None):
        transfer.with_user(user or self.user_transfer).with_context(
            allowed_company_ids=(user or self.user_transfer).company_id.ids
        ).action_cancel()

    def _payments(self, transfer):
        return transfer.origin_payment_id | transfer.destination_payment_id

    def test_cancel(self):
        transfer = self._transfer()
        self._cancel(transfer)
        self.assertEqual(transfer.state, "cancelled")
        for payment in self._payments(transfer):
            self.assertEqual(payment.state, "canceled")
            self.assertEqual(payment.move_id.state, "cancel")
        self.assertIn("Transfer cancelled", transfer.message_ids[0].body)
        with self.assertRaisesRegex(UserError, "Only posted intercompany transfers"):
            self._cancel(transfer)
        with self.assertRaisesRegex(UserError, "Only the memo"):
            transfer.with_user(self.user_transfer).write({"state": "posted"})

    def test_cancel_blocked_by_statement(self):
        for side in ("origin_payment_id", "destination_payment_id"):
            with self.subTest(side=side):
                transfer = self._transfer()
                payment = transfer[side]
                st_line = self._reconcile_with_statement(payment)
                with self.assertRaisesRegex(UserError, "can't be cancelled") as error:
                    self._cancel(transfer)
                self.assertIn(payment.name, str(error.exception))
                self.assertIn(payment.company_id.name, str(error.exception))
                self.assertIn(st_line.display_name, str(error.exception))
                self.assertEqual(transfer.state, "posted")
                self.assertFalse(self._payments(transfer).filtered(lambda p: p.state == "canceled"))

    def test_cancel_blocked_by_closed_period(self):
        transfer = self._transfer()
        self.company_b.fiscalyear_lock_date = self.today
        with self.assertRaisesRegex(UserError, "Company B is dated in a closed period"):
            self._cancel(transfer)
        self.assertEqual(transfer.state, "posted")

    def test_cancel_is_atomic(self):
        transfer = self._transfer()
        original_cancel = AccountPayment.action_cancel
        company_b = self.company_b

        def action_cancel(payments):
            if payments.company_id == company_b:
                raise UserError("Destination failure")
            return original_cancel(payments)

        # The savepoint stands for the request's transaction, which an error
        # rolls back entirely (assertRaisesRegex doesn't roll back itself).
        with patch.object(AccountPayment, "action_cancel", action_cancel), self.assertRaisesRegex(
            UserError, "Destination failure"
        ), self.env.cr.savepoint():
            self._cancel(transfer)
        self.env.invalidate_all()
        self.assertEqual(transfer.state, "posted")
        self.assertEqual(set(self._payments(transfer).mapped("state")), {"in_process"})
        self.assertEqual(set(self._payments(transfer).move_id.mapped("state")), {"posted"})

    def test_cancel_requires_both_companies(self):
        transfer = self._transfer()
        with self.assertRaisesRegex(AccessError, "Both companies"):
            self._cancel(transfer, user=self.user_only_a)
        with self.assertRaises(AccessError):
            self._cancel(transfer, user=self.user_no_group)
