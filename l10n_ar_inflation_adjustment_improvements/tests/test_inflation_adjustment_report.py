import io
from collections import defaultdict

import openpyxl

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

D = fields.Date.to_date


@tagged("post_install", "-at_install")
class TestInflationAdjustmentReport(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adjustment_journal = cls.env["account.journal"].create({
            "name": "Inflation adjustment", "code": "TINF", "type": "general",
        })
        cls.journal = cls.env["account.journal"].create({"name": "Misc test", "code": "TMSC", "type": "general"})
        Account = cls.env["account.account"]
        cls.fixed_asset = Account.create({
            "code": "1.9.9.001", "name": "Test fixed asset", "account_type": "asset_fixed", "is_monetary": False,
        })
        cls.cash = Account.create({
            "code": "1.9.9.002", "name": "Test cash", "account_type": "asset_current", "is_monetary": True,
        })
        cls.capital = Account.create({
            "code": "3.9.9.001", "name": "Test capital", "account_type": "equity", "is_monetary": False,
        })
        cls.sales = Account.create({
            "code": "4.9.9.002", "name": "Test sales", "account_type": "income", "is_monetary": False,
        })
        cls.partner_account = Account.create({
            "code": "2.9.9.001", "name": "Test partner current account", "account_type": "equity",
            "is_monetary": False, "reconcile": True,
        })
        cls.recpam = Account.create({
            "code": "4.9.9.001", "name": "Test RECPAM", "account_type": "income_other", "is_monetary": True,
        })
        # First fiscal year in Odoo: opening entry plus a few movements
        cls.opening = cls._move("2025-01-01", [(cls.fixed_asset, 1000.0), (cls.capital, -700.0), (cls.cash, -300.0)])
        cls._move("2025-03-15", [(cls.cash, 333.33), (cls.sales, -333.33)])
        cls._move("2025-03-20", [(cls.cash, 166.67), (cls.sales, -166.67)])
        cls._move("2025-05-10", [(cls.partner_account, 250.0), (cls.cash, -250.0)], partner=cls.partner_a)

    @classmethod
    def _move(cls, date, lines, partner=None):
        move = cls.env["account.move"].create({
            "journal_id": cls.journal.id,
            "date": date,
            "line_ids": [
                Command.create({
                    "account_id": account.id,
                    "debit": max(amount, 0.0),
                    "credit": max(-amount, 0.0),
                    "partner_id": partner.id if partner else False,
                })
                for account, amount in lines
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
            "open_cloure_entry": "yes",
            "first_odoo_fiscal_year": "yes",
            "opening_move_ids": [Command.set(self.opening.ids)],
            **vals,
        })

    def _entry_adjustments(self, move):
        adjustments = defaultdict(float)
        for line in move.line_ids.filtered(lambda l: l.account_id != self.recpam):
            adjustments[line.account_id] += line.balance
        return adjustments

    def test_simulation_matches_entry(self):
        wizard = self._wizard()
        moves_before = self.env["account.move"].search_count([])
        report = wizard._get_adjustment_report_data()
        # Nothing is left behind by the simulation
        self.assertEqual(self.env["account.move"].search_count([]), moves_before)

        move = self.env["account.move"].browse(wizard.confirm()["res_id"])
        adjustments = self._entry_adjustments(move)
        reported = {line["account"]: line for line in report["accounts"]}
        self.assertEqual(set(reported), set(adjustments))
        for account, adjustment in adjustments.items():
            line = reported[account]
            self.assertAlmostEqual(line["adjustment"], adjustment, places=2)
            self.assertAlmostEqual(line["restated"], line["balance"] + adjustment, places=2)
            # Each detail level adds up to the entry
            self.assertAlmostEqual(sum(m["adjustment"] for m in line["months"]), adjustment, places=2)
            entries = sum(e["adjustment_debit"] - e["adjustment_credit"] for e in line["entries"])
            self.assertAlmostEqual(entries + line["rounding"], adjustment, places=2)
        self.assertAlmostEqual(
            report["recpam"], sum(move.line_ids.filtered(lambda l: l.account_id == self.recpam).mapped("balance")), places=2
        )
        self.assertAlmostEqual(report["recpam"], -report["total_adjustment"], places=2)

    def test_report_details(self):
        report = self._wizard()._get_adjustment_report_data()
        # The report documents which entries were taken as opening
        self.assertEqual(len(report["entries_info"]), 1)
        self.assertEqual(report["entries_info"][0][1], self.opening.name)
        fixed_asset = next(line for line in report["accounts"] if line["account"] == self.fixed_asset)
        # The opening entry as initial balance, with the index of the month before the start date
        self.assertEqual(len(fixed_asset["months"]), 1)
        self.assertEqual(fixed_asset["months"][0]["month"], D("2024-12-01"))
        self.assertEqual(fixed_asset["entries"][0]["name"], self.opening.name)
        sales = next(line for line in report["accounts"] if line["account"] == self.sales)
        # One month, two entries
        self.assertEqual([m["month"] for m in sales["months"]], [D("2025-03-01")])
        self.assertEqual(len(sales["entries"]), 2)

    def test_mixed_detail(self):
        """Balance sheet accounts by entry, income/expense accounts by month."""
        wizard = self._wizard()
        sales_moves = self.env["account.move.line"].search([("account_id", "=", self.sales.id)]).move_id
        html = {}
        for detail in ("month", "mixed", "entry"):
            content, _type = self.env["ir.actions.report"]._render_qweb_html(
                "l10n_ar_inflation_adjustment_improvements.action_report_inflation_adjustment",
                wizard.ids,
                data={"detail": detail},
            )
            html[detail] = content.decode()
        # The opening entry is listed in the header, and shows up by name on
        # its balance sheet accounts' rows only when detailed by entry
        self.assertEqual(html["month"].count(self.opening.name), 1)
        self.assertGreater(html["mixed"].count(self.opening.name), 1)
        self.assertGreater(html["entry"].count(self.opening.name), 1)
        # The sales entries only in the full detail by entry
        for move in sales_moves:
            self.assertNotIn(move.name, html["mixed"])
            self.assertIn(move.name, html["entry"])
        self.assertIn("03/2025", html["mixed"])

    def test_confirm_attaches_report_files(self):
        move = self.env["account.move"].browse(self._wizard().confirm()["res_id"])
        attachments = self.env["ir.attachment"].search([("res_model", "=", "account.move"), ("res_id", "=", move.id)])
        self.assertEqual(len(attachments), 2)
        xlsx = attachments.filtered(lambda a: a.name.endswith(".xlsx"))
        workbook = openpyxl.load_workbook(io.BytesIO(xlsx.raw))
        self.assertEqual(len(workbook.sheetnames), 4)

    def test_simulate_buttons(self):
        wizard = self._wizard()
        moves_before = self.env["account.move"].search_count([])
        for action in (wizard.action_simulate_pdf(), wizard.action_simulate_xlsx()):
            self.assertEqual(action["type"], "ir.actions.act_url")
            self.assertEqual(action["target"], "download")
        self.assertEqual(self.env["account.move"].search_count([]), moves_before)

    def test_monetary_review(self):
        wizard = self._wizard()
        review = wizard._get_monetary_review_accounts()
        # Reconcilable, with partner movements in journal entries
        self.assertEqual(len(review[self.partner_account]), 2)
        self.assertNotIn(self.fixed_asset, review)
        self.assertNotIn(self.sales, review)
        self.assertIn(self.partner_account.code, wizard.monetary_review_warning)

        self.partner_account.inflation_monetary_reviewed = True
        wizard.invalidate_recordset(["monetary_review_warning"])
        self.assertNotIn(self.partner_account, wizard._get_monetary_review_accounts())
        self.assertFalse(wizard.monetary_review_warning)
