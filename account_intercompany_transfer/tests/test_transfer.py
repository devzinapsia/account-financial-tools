from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.models.account_payment import AccountPayment

from ..models.account_payment import FOREIGN_TRANSFER_MARKERS
from .common import IntercompanyTransferCommon


@tagged("post_install", "-at_install")
class TestIntercompanyTransfer(IntercompanyTransferCommon):
    # ------------------------------------------------------------------
    # Wizard options
    # ------------------------------------------------------------------

    def _wizard(self, user=None, **vals):
        return self._as_user("account.intercompany.transfer.wizard", user).new(vals)

    def test_wizard_options(self):
        wizard = self._wizard()
        origin_ids = wizard.origin_journal_domain[0][2]
        self.assertIn(self.cash_a.id, origin_ids)
        self.assertIn(self.bank_b.id, origin_ids, "Journals of allowed companies not ticked are offered.")
        self.assertNotIn(self.cash_c.id, origin_ids, "Company C has no bridge account.")

        wizard.origin_journal_id = self.cash_a
        self.assertEqual(wizard.company_id, self.company_a)
        self.assertEqual(wizard.currency_id, self.currency)
        self.assertEqual(
            wizard.destination_company_domain,
            [("id", "in", self.company_b.ids)],
            "Neither the origin company nor a company without bridge account is offered.",
        )
        wizard.destination_company_id = self.company_b
        destination_ids = wizard.destination_journal_domain[0][2]
        self.assertEqual(set(destination_ids), {self.cash_b.id, self.bank_b.id})

    def test_wizard_options_other_currency(self):
        other_currency = self.setup_other_currency("EUR")
        self.bank_b.currency_id = other_currency
        wizard = self._wizard(origin_journal_id=self.cash_a.id, destination_company_id=self.company_b.id)
        self.assertEqual(wizard.destination_journal_domain, [("id", "in", self.cash_b.ids)])

    def test_wizard_options_outside_allowed_companies(self):
        wizard = self._wizard(user=self.user_only_a, origin_journal_id=self.cash_a.id)
        self.assertEqual(wizard.origin_journal_domain[0][2], self.env["account.journal"].search(
            [("company_id", "=", self.company_a.id), ("type", "in", ("bank", "cash"))]
        ).ids)
        self.assertEqual(wizard.destination_company_domain, [("id", "in", [])])

    def test_wizard_confirm(self):
        wizard = self._as_user("account.intercompany.transfer.wizard").create(
            {
                "origin_journal_id": self.cash_a.id,
                "destination_company_id": self.company_b.id,
                "destination_journal_id": self.cash_b.id,
                "amount": 250.0,
                "memo": "From the wizard",
            }
        )
        action = wizard.action_confirm()
        self.assertEqual(action["res_model"], "account.intercompany.transfer")
        transfer = self.env["account.intercompany.transfer"].browse(action["res_id"])
        self.assertEqual(transfer.amount, 250.0)
        self.assertEqual(transfer.user_id, self.user_transfer)

    def test_wizard_destination_company_mismatch(self):
        wizard = self._as_user("account.intercompany.transfer.wizard").create(
            {
                "origin_journal_id": self.cash_a.id,
                "destination_company_id": self.company_c.id,
                "destination_journal_id": self.cash_b.id,
                "amount": 10.0,
            }
        )
        with self.assertRaisesRegex(ValidationError, "does not belong to Company C"):
            wizard.action_confirm()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def _assert_entry(self, payment, debit_account, credit_account, partner):
        lines = payment.move_id.line_ids
        self.assertEqual(len(lines), 2)
        debit = lines.filtered(lambda line: line.debit)
        credit = lines.filtered(lambda line: line.credit)
        self.assertEqual(debit.account_id, debit_account)
        self.assertEqual(credit.account_id, credit_account)
        self.assertEqual(debit.debit, 10000.0)
        self.assertEqual(credit.credit, 10000.0)
        self.assertEqual(lines.partner_id, partner)
        self.assertEqual(lines.currency_id, self.currency)
        self.assertEqual(payment.move_id.date, self.today)
        self.assertEqual(payment.move_id.state, "posted")

    def test_transfer(self):
        transfer = self._transfer()
        origin, destination = transfer.origin_payment_id, transfer.destination_payment_id
        self.assertEqual(transfer.state, "posted")
        self.assertEqual(transfer.company_id, self.company_a)
        self.assertEqual(transfer.destination_company_id, self.company_b)
        self.assertEqual(transfer.user_id, self.user_transfer)
        self.assertTrue(transfer.name.startswith(f"ICT/{self.today.year}/"))

        self.assertEqual(origin.company_id, self.company_a)
        self.assertEqual(origin.journal_id, self.cash_a)
        self.assertEqual(origin.payment_type, "outbound")
        self.assertEqual(destination.company_id, self.company_b)
        self.assertEqual(destination.journal_id, self.cash_b)
        self.assertEqual(destination.payment_type, "inbound")
        for payment in origin | destination:
            self.assertEqual(payment.state, "in_process")
            self.assertEqual(payment.amount, 10000.0)
            self.assertEqual(payment.currency_id, self.currency)
            self.assertEqual(payment.date, self.today)
            self.assertEqual(payment.memo, f"{transfer.name} - Funding")
            self.assertEqual(payment.intercompany_transfer_id, transfer)
            self.assertEqual(payment.payment_method_line_id.payment_method_id.code, "manual")

        self._assert_entry(
            origin,
            debit_account=self.bridge_a,
            credit_account=origin.outstanding_account_id,
            partner=self.company_b.partner_id,
        )
        self._assert_entry(
            destination,
            debit_account=destination.outstanding_account_id,
            credit_account=self.bridge_b,
            partner=self.company_a.partner_id,
        )

    def test_no_foreign_transfer_markers(self):
        transfer = self._transfer()
        for payment in transfer.origin_payment_id | transfer.destination_payment_id:
            self.assertFalse(payment._get_foreign_transfer_markers())
            for name in FOREIGN_TRANSFER_MARKERS:
                if name in payment._fields:
                    self.assertFalse(payment[name], f"{name} must not be set on {payment.name}")
            self.assertNotEqual(payment.destination_account_id, payment.company_id.transfer_account_id)

    def test_numbering_per_company(self):
        first = self._transfer()
        second = self._transfer()
        from_b = self._transfer(origin=self.cash_b, destination=self.cash_a)
        prefix = f"ICT/{self.today.year}/"
        number = int(first.name.removeprefix(prefix))
        self.assertEqual(second.name, f"{prefix}{number + 1:05d}")
        self.assertEqual(from_b.name, f"{prefix}00001", "Company B has its own numbering.")
        next_year = self._transfer(date=date(self.today.year + 1, 1, 5))
        self.assertEqual(next_year.name, f"ICT/{self.today.year + 1}/00001")

    def test_single_company_ticked(self):
        """The usual case: only the origin company is ticked in the switcher."""
        transfer = self._as_user("account.intercompany.transfer", ticked=self.company_a)._create_transfer(
            self.cash_a, self.cash_b, 100.0, self.today
        )
        self.assertEqual(transfer.sudo().destination_payment_id.company_id, self.company_b)

    # ------------------------------------------------------------------
    # Validations
    # ------------------------------------------------------------------

    def test_same_company(self):
        with self.assertRaisesRegex(ValidationError, "must be different"):
            self._transfer(destination=self.bank_a)

    def test_amount(self):
        for amount in (0.0, -10.0):
            with self.subTest(amount=amount), self.assertRaisesRegex(ValidationError, "greater than zero"):
                self._transfer(amount=amount)

    def test_destination_without_bridge_account(self):
        self.user_transfer.company_ids |= self.company_c
        with self.assertRaisesRegex(ValidationError, "Company C has no intercompany transfer bridge account"):
            self._transfer(destination=self.cash_c)

    def test_currency_mismatch(self):
        other_currency = self.setup_other_currency("EUR")
        self.bank_b.currency_id = other_currency
        with self.assertRaisesRegex(ValidationError, rf"is in {self.currency.name} .* is in EUR"):
            self._transfer(destination=self.bank_b)

    def test_payment_method_without_outstanding_account(self):
        self.cash_b.inbound_payment_method_line_ids.payment_account_id = False
        with self.assertRaisesRegex(UserError, "has no outstanding account"):
            self._transfer()

    # ------------------------------------------------------------------
    # Atomicity
    # ------------------------------------------------------------------

    def _count_records(self):
        return (
            self.env["account.intercompany.transfer"].search_count([]),
            self.env["account.payment"].search_count([]),
            self.env["account.move"].search_count([]),
        )

    def test_closed_period_in_destination(self):
        before = self._count_records()
        self.company_b.fiscalyear_lock_date = self.today
        with self.assertRaisesRegex(UserError, "closed period of Company B"):
            self._transfer()
        self.assertEqual(self._count_records(), before)

    def test_failure_in_destination_leaves_nothing(self):
        """A failure while posting the destination payment, after the
        origin payment was posted, rolls everything back, numbering included.
        """
        before = self._count_records()
        original_post = AccountPayment.action_post
        company_b = self.company_b

        def action_post(payments):
            if payments.company_id == company_b:
                raise UserError("Destination failure")
            return original_post(payments)

        # The savepoint stands for the request's transaction, which an error
        # rolls back entirely (assertRaisesRegex doesn't roll back itself).
        with patch.object(AccountPayment, "action_post", action_post), self.assertRaisesRegex(
            UserError, "Destination failure"
        ), self.env.cr.savepoint():
            self._transfer()
        self.env.invalidate_all()
        self.assertEqual(self._count_records(), before)
        self.assertEqual(self._transfer().name, f"ICT/{self.today.year}/00001", "No gap in the numbering.")

    # ------------------------------------------------------------------
    # Bank reconciliation
    # ------------------------------------------------------------------

    def test_no_double_count(self):
        transfer = self._transfer()
        origin = transfer.origin_payment_id
        liquidity_account = self.cash_a.default_account_id

        def cash_balance():
            lines = self.env["account.move.line"].search(
                [("account_id", "=", liquidity_account.id), ("parent_state", "=", "posted")]
            )
            return sum(lines.mapped("balance"))

        before = cash_balance()
        self.assertFalse(origin.move_id.line_ids.filtered(lambda line: line.account_id == liquidity_account))
        self._reconcile_with_statement(origin)
        self.assertEqual(cash_balance() - before, -10000.0, "The cash account moves once, through the statement.")
        self.assertTrue(origin.is_matched)
        self.assertEqual(origin.state, "paid")
