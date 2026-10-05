from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

# The adjustment period (Jan-Mar 2025) and the month before it (Dec 2024)
# are covered by the indexes l10n_ar_account_reports loads as data.


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
        cls.misc_journal = cls.company_data["default_journal_misc"]

        cls.non_monetary_account = cls.env["account.account"].create({
            "code": "1.9.9.001",
            "name": "Test fixed asset",
            "account_type": "asset_fixed",
            "is_monetary": False,
        })
        cls.monetary_account = cls.env["account.account"].create({
            "code": "1.9.9.002",
            "name": "Test cash",
            "account_type": "asset_current",
            "is_monetary": True,
        })
        cls.adjustment_account = cls.env["account.account"].create({
            "code": "4.9.9.001",
            "name": "Test RECPAM",
            "account_type": "income_other",
            "is_monetary": True,
        })

        # Only closing/opening journal entries inside the adjusted range (or
        # before it, for the initial balance); the regular entry is dated after
        # it, so it only shows up in the domain tests, not in confirm()
        cls.previous_closing_move = cls._create_move(cls.closing_journal, "2024-12-31", 100.0)
        cls.opening_move = cls._create_move(cls.closing_journal, "2025-01-01", 200.0)
        cls.other_closing_journal_move = cls._create_move(cls.closing_journal, "2025-02-15", 300.0)
        cls.closing_move = cls._create_move(cls.closing_journal, "2025-03-31", 400.0)
        cls.regular_move = cls._create_move(cls.misc_journal, "2025-06-10", 500.0)

    @classmethod
    def _create_move(cls, journal, date, amount):
        move = cls.env["account.move"].create({
            "journal_id": journal.id,
            "date": date,
            "line_ids": [
                Command.create({"account_id": cls.non_monetary_account.id, "debit": amount}),
                Command.create({"account_id": cls.monetary_account.id, "credit": amount}),
            ],
        })
        move.action_post()
        return move

    def _create_wizard(self, **vals):
        return self.env["inflation.adjustment"].create({
            "company_id": self.env.company.id,
            "date_from": fields.Date.to_date("2025-01-01"),
            "date_to": fields.Date.to_date("2025-03-31"),
            "journal_id": self.adjustment_journal.id,
            "account_id": self.adjustment_account.id,
            **vals,
        })

    def _adjusted_moves(self, wizard):
        return self.env["account.move.line"].search(wizard.get_move_line_domain()).move_id

    def test_no_closing_entries_excludes_nothing(self):
        wizard = self._create_wizard(open_cloure_entry="no")
        moves = self._adjusted_moves(wizard)
        self.assertEqual(
            moves,
            self.previous_closing_move + self.opening_move + self.other_closing_journal_move
            + self.closing_move + self.regular_move,
        )

    def test_individual_entries_excludes_only_given_entries(self):
        wizard = self._create_wizard(
            open_cloure_entry="yes",
            specify_individual_entries="yes",
            closure_move_id=self.closing_move.id,
            open_move_id=self.opening_move.id,
        )
        moves = self._adjusted_moves(wizard)
        self.assertNotIn(self.closing_move, moves)
        self.assertNotIn(self.opening_move, moves)
        self.assertIn(self.previous_closing_move, moves)
        self.assertIn(self.other_closing_journal_move, moves)
        self.assertIn(self.regular_move, moves)

    def test_whole_journal_excludes_every_entry_in_it(self):
        wizard = self._create_wizard(
            open_cloure_entry="yes",
            specify_individual_entries="no",
            exclusion_journal_id=self.closing_journal.id,
        )
        self.assertEqual(self._adjusted_moves(wizard), self.regular_move)

    def test_confirm_whole_journal_excludes_initial_balance_and_periods(self):
        # Without exclusions the closing journal entries (initial balance and
        # periods) get adjusted...
        move_action = self._create_wizard(open_cloure_entry="no").confirm()
        adjustment_move = self.env["account.move"].browse(move_action["res_id"])
        self.assertTrue(adjustment_move.line_ids.filtered(lambda l: l.account_id == self.non_monetary_account))
        # ... and excluding that journal leaves nothing to adjust at all
        wizard = self._create_wizard(
            open_cloure_entry="yes",
            specify_individual_entries="no",
            exclusion_journal_id=self.closing_journal.id,
        )
        with self.assertRaisesRegex(UserError, "No journal entries to adjust"):
            wizard.with_context(lang="en_US").confirm()

    def test_whole_journal_requires_journal(self):
        with self.assertRaises(ValidationError):
            self._create_wizard(open_cloure_entry="yes", specify_individual_entries="no")
        # Not required when the closing/opening question is answered no
        self._create_wizard(open_cloure_entry="no", specify_individual_entries="no")

    def test_whole_journal_cannot_be_adjustment_journal(self):
        with self.assertRaises(ValidationError):
            self._create_wizard(
                open_cloure_entry="yes",
                specify_individual_entries="no",
                exclusion_journal_id=self.adjustment_journal.id,
            )

    def test_confirm_ignores_hidden_individual_entries(self):
        # Wizard filled in bypassing the form: the closing entry set doesn't
        # belong to the selected branch and must not be excluded on its own
        wizard = self._create_wizard(
            open_cloure_entry="yes",
            specify_individual_entries="no",
            exclusion_journal_id=self.misc_journal.id,
            closure_move_id=self.closing_move.id,
        )
        wizard.confirm()
        self.assertFalse(wizard.closure_move_id)
        self.assertIn(self.closing_move, self._adjusted_moves(wizard))

    def test_onchange_clears_hidden_fields(self):
        with Form(self.env["inflation.adjustment"]) as wizard_form:
            wizard_form.journal_id = self.adjustment_journal
            wizard_form.account_id = self.adjustment_account
            wizard_form.open_cloure_entry = "yes"
            wizard_form.specify_individual_entries = "yes"
            wizard_form.closure_move_id = self.closing_move
            wizard_form.open_move_id = self.opening_move
            wizard_form.specify_individual_entries = "no"
            self.assertFalse(wizard_form.closure_move_id)
            self.assertFalse(wizard_form.open_move_id)
            wizard_form.exclusion_journal_id = self.closing_journal
            wizard_form.open_cloure_entry = "no"
            self.assertFalse(wizard_form.exclusion_journal_id)
