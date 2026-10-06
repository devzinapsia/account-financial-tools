from odoo import fields
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

D = fields.Date.to_date

# The adjusted fiscal year (2025) and the month before it (Dec 2024) are
# covered by the indexes l10n_ar_account_reports loads as data.


@tagged("post_install", "-at_install")
class TestInflationAdjustmentImprovements(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adjustment_journal = cls.env["account.journal"].create({
            "name": "Inflation adjustment",
            "code": "TINF",
            "type": "general",
        })
        cls.closing_journal = cls.env["account.journal"].create({
            "name": "Closing/opening",
            "code": "TCLO",
            "type": "general",
        })
        Account = cls.env["account.account"]
        cls.fixed_asset = Account.create({
            "code": "1.9.9.001", "name": "Test fixed asset", "account_type": "asset_fixed", "is_monetary": False,
        })
        cls.cash = Account.create({
            "code": "1.9.9.002", "name": "Test cash", "account_type": "asset_current", "is_monetary": True,
        })
        cls.bridge = Account.create({
            "code": "3.9.9.009", "name": "Test opening bridge", "account_type": "equity", "is_monetary": False,
        })
        cls.recpam = Account.create({
            "code": "4.9.9.001", "name": "Test RECPAM", "account_type": "income_other", "is_monetary": True,
        })
        index = cls.env["inflation.adjustment.index"]
        end_value = index.find(D("2025-12-01")).value
        cls.initial_factor = end_value / index.find(D("2024-12-01")).value - 1.0
        cls.march_factor = end_value / index.find(D("2025-03-01")).value - 1.0

    def _move(self, date, debit_account, credit_account, amount):
        move = self.env["account.move"].create({
            "journal_id": self.closing_journal.id,
            "date": date,
            "line_ids": [
                Command.create({"account_id": debit_account.id, "debit": amount}),
                Command.create({"account_id": credit_account.id, "credit": amount}),
            ],
        })
        move.action_post()
        return move

    def _wizard(self, **vals):
        return self.env["inflation.adjustment"].create({
            "company_id": self.env.company.id,
            "date_from": D("2025-01-01"),
            "date_to": D("2025-12-31"),
            "journal_id": self.adjustment_journal.id,
            "account_id": self.recpam.id,
            **vals,
        })

    def _normal_year_wizard(self, closings, openings):
        return self._wizard(
            open_cloure_entry="yes",
            first_odoo_fiscal_year="no",
            closing_move_ids=[Command.set(closings.ids)],
            opening_move_ids=[Command.set(openings.ids)],
        )

    def _first_year_wizard(self, openings, **vals):
        return self._wizard(
            open_cloure_entry="yes",
            first_odoo_fiscal_year="yes",
            opening_move_ids=[Command.set(openings.ids)],
            **vals,
        )

    def _adjustment(self, wizard, account):
        move = self.env["account.move"].browse(wizard.confirm()["res_id"])
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0)
        return sum(move.line_ids.filtered(lambda l: l.account_id == account).mapped("balance"))

    # Upstream behaviors that must stay as they are

    def test_new_business(self):
        """No balances to open: each movement adjusted from its own month."""
        self._move("2025-03-15", self.fixed_asset, self.cash, 1000.0)
        wizard = self._wizard(open_cloure_entry="no")
        self.assertAlmostEqual(self._adjustment(wizard, self.fixed_asset), 1000.0 * self.march_factor, delta=0.01)

    def test_normal_year_single_entries(self):
        self._move("2024-01-01", self.fixed_asset, self.cash, 1000.0)
        closing = self._move("2024-12-31", self.cash, self.fixed_asset, 1000.0)
        opening = self._move("2025-01-01", self.fixed_asset, self.cash, 1000.0)
        wizard = self._normal_year_wizard(closing, opening)
        self.assertFalse(wizard.adjustment_warning)
        self.assertAlmostEqual(self._adjustment(wizard, self.fixed_asset), 1000.0 * self.initial_factor, delta=0.01)

    # Regular fiscal year with several entries

    def test_normal_year_several_openings(self):
        self._move("2024-01-01", self.fixed_asset, self.cash, 1000.0)
        closing = self._move("2024-12-31", self.cash, self.fixed_asset, 1000.0)
        openings = (
            self._move("2025-01-01", self.fixed_asset, self.cash, 600.0)
            + self._move("2025-01-20", self.fixed_asset, self.cash, 400.0)
        )
        wizard = self._normal_year_wizard(closing, openings)
        self.assertFalse(wizard.adjustment_warning)
        self.assertAlmostEqual(self._adjustment(wizard, self.fixed_asset), 1000.0 * self.initial_factor, delta=0.01)

    def test_normal_year_missing_opening_warning(self):
        self._move("2024-01-01", self.fixed_asset, self.cash, 1000.0)
        closing = self._move("2024-12-31", self.cash, self.fixed_asset, 1000.0)
        opening = self._move("2025-01-01", self.fixed_asset, self.cash, 600.0)
        self._move("2025-01-20", self.fixed_asset, self.cash, 400.0)
        wizard = self._normal_year_wizard(closing, opening)
        self.assertIn(self.fixed_asset.code, wizard.adjustment_warning)
        # Only a warning: the adjustment can still be confirmed
        wizard.confirm()

    # First fiscal year in Odoo

    def test_first_year_opening_as_initial_balance(self):
        """No closing nor any other movement: the opening entry is the
        initial balance (upstream can't adjust it right in any way)."""
        opening = self._move("2025-01-01", self.fixed_asset, self.cash, 1000.0)
        wizard = self._first_year_wizard(opening)
        self.assertFalse(wizard.adjustment_warning)
        self.assertAlmostEqual(self._adjustment(wizard, self.fixed_asset), 1000.0 * self.initial_factor, delta=0.01)

    def test_first_year_with_pending_invoices(self):
        """Pending invoices loaded before the start date against a bridge
        account the opening entry cancels: they don't change the result."""
        self._move("2024-12-20", self.cash, self.bridge, 300.0)
        opening = self.env["account.move"].create({
            "journal_id": self.closing_journal.id,
            "date": D("2025-01-01"),
            "line_ids": [
                Command.create({"account_id": self.fixed_asset.id, "debit": 1000.0}),
                Command.create({"account_id": self.bridge.id, "debit": 300.0}),
                Command.create({"account_id": self.cash.id, "credit": 1300.0}),
            ],
        })
        opening.action_post()
        # Regular movement of the period, so that upstream also generates lines
        self._move("2025-03-15", self.fixed_asset, self.cash, 500.0)
        wizard = self._first_year_wizard(opening)
        self.assertFalse(wizard.adjustment_warning)
        move = self.env["account.move"].browse(wizard.confirm()["res_id"])
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0)
        fixed_asset = sum(move.line_ids.filtered(lambda l: l.account_id == self.fixed_asset).mapped("balance"))
        self.assertAlmostEqual(
            fixed_asset, 1000.0 * self.initial_factor + 500.0 * self.march_factor, delta=0.02
        )
        bridge = sum(move.line_ids.filtered(lambda l: l.account_id == self.bridge).mapped("balance"))
        self.assertAlmostEqual(bridge, 0.0, delta=0.01)

    def test_first_year_prior_balance_warning(self):
        """A balance before the start date that the opening entry also
        includes would be counted twice."""
        self._move("2024-06-01", self.fixed_asset, self.cash, 1000.0)
        opening = self._move("2025-01-01", self.fixed_asset, self.cash, 1000.0)
        wizard = self._first_year_wizard(opening)
        self.assertIn(self.fixed_asset.code, wizard.adjustment_warning)

    # Validations

    def test_required_entries(self):
        opening = self._move("2025-01-01", self.fixed_asset, self.cash, 1000.0)
        with self.assertRaises(ValidationError):
            self._normal_year_wizard(self.env["account.move"], opening)
        with self.assertRaises(ValidationError):
            self._first_year_wizard(self.env["account.move"])
        # Nothing required when the closing/opening question is answered no
        self._wizard(open_cloure_entry="no")

    def test_entries_dates(self):
        prev_closing = self._move("2024-12-31", self.cash, self.fixed_asset, 1000.0)
        opening = self._move("2025-01-01", self.fixed_asset, self.cash, 1000.0)
        curr_closing = self._move("2025-12-31", self.cash, self.fixed_asset, 1000.0)
        # Current fiscal year's closing instead of the previous one's
        with self.assertRaises(ValidationError):
            self._normal_year_wizard(curr_closing, opening)
        # Opening entry outside the adjusted period
        with self.assertRaises(ValidationError):
            self._normal_year_wizard(prev_closing, prev_closing)

    def test_confirm_clears_hidden_closings(self):
        """Wizard filled in bypassing the form: closings selected on a first
        fiscal year must not be excluded."""
        prev_closing = self._move("2024-12-31", self.cash, self.fixed_asset, 1000.0)
        opening = self._move("2025-01-01", self.fixed_asset, self.cash, 1000.0)
        wizard = self._first_year_wizard(opening, closing_move_ids=[Command.set(prev_closing.ids)])
        wizard.confirm()
        self.assertFalse(wizard.closing_move_ids)
        self.assertIn(prev_closing, self.env["account.move.line"].search(wizard.get_move_line_domain()).move_id)

    def test_onchange_clears_hidden_fields(self):
        prev_closing = self._move("2024-12-31", self.cash, self.fixed_asset, 1000.0)
        opening = self._move("2025-01-01", self.fixed_asset, self.cash, 1000.0)
        with Form(self.env["inflation.adjustment"]) as wizard_form:
            wizard_form.date_from = D("2025-01-01")
            wizard_form.date_to = D("2025-12-31")
            wizard_form.journal_id = self.adjustment_journal
            wizard_form.account_id = self.recpam
            wizard_form.open_cloure_entry = "yes"
            wizard_form.closing_move_ids.add(prev_closing)
            wizard_form.opening_move_ids.add(opening)
            wizard_form.first_odoo_fiscal_year = "yes"
            self.assertFalse(wizard_form.closing_move_ids)
            self.assertEqual(len(wizard_form.opening_move_ids), 1)
            wizard_form.open_cloure_entry = "no"
            self.assertFalse(wizard_form.opening_move_ids)
