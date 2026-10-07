import io
from collections import defaultdict
from datetime import timedelta

import xlsxwriter
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools.misc import format_date, formatLang

REPORT = "l10n_ar_inflation_adjustment_improvements.action_report_inflation_adjustment"
XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NON_CURRENT_TYPES = ("asset_non_current", "liability_non_current")


class _SimulationRollback(Exception):
    """Raised to roll back the adjustment entry created only to simulate it."""


class InflationAdjustment(models.TransientModel):
    _inherit = "inflation.adjustment"

    report_detail = fields.Selection(
        [
            ("month", "By account and month"),
            ("mixed", "Balance sheet accounts by entry, income/expense by month"),
            ("entry", "By account and entry"),
        ],
        string="Report detail",
        default="month",
        required=True,
        help="Detail of the PDF report: by account and month, as the adjustment entry lines; by journal entry on"
        " balance sheet accounts and by month on income/expense accounts, which hold every invoice; or by"
        " account and journal entry. The Excel file always has the by month and by entry details.",
    )
    monetary_review_warning = fields.Html(
        string="Accounts to review",
        compute="_compute_monetary_review_warning",
        sanitize=False,
    )

    # Accounts to review

    def _get_monetary_review_accounts(self):
        """Return {account: [reasons]} of the non-monetary accounts the
        adjustment reaches that look monetary (e.g. receivables or payables in
        pesos) and nobody reviewed yet."""
        self.ensure_one()
        if not (self.company_id and self.date_to):
            return {}
        AccountMoveLine = self.env["account.move.line"]
        domain = [
            ("account_id.is_monetary", "=", False),
            ("account_id.inflation_monetary_reviewed", "=", False),
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),
            ("date", "<=", self.date_to),
        ]
        accounts = self.env["account.account"].union(
            *(account for account, in AccountMoveLine._read_group(domain, ["account_id"]))
        )
        # Invoice lines carry the partner too: only journal entries (manual
        # entries, payments) tell a balance with a third party apart
        with_partner = self.env["account.account"].union(*(
            account for account, in AccountMoveLine._read_group(
                domain + [
                    ("partner_id", "!=", False),
                    ("move_id.move_type", "=", "entry"),
                    ("account_id.internal_group", "in", ("asset", "liability", "equity")),
                ],
                ["account_id"],
            )
        ))
        company_currency = self.company_id.currency_id
        result = {}
        for account in accounts.sorted(lambda a: a.code or ""):
            reasons = []
            if account.reconcile:
                reasons.append(_("allows reconciliation"))
            if account.account_type in NON_CURRENT_TYPES:
                reasons.append(_("non-current asset/liability type"))
            if account.currency_id and account.currency_id != company_currency:
                reasons.append(_("foreign currency"))
            if account in with_partner:
                reasons.append(_("journal entries with a partner"))
            if reasons:
                result[account] = reasons
        return result

    @api.depends("company_id", "date_to")
    def _compute_monetary_review_warning(self):
        for wizard in self:
            accounts = wizard._get_monetary_review_accounts()
            if not accounts:
                wizard.monetary_review_warning = False
                continue
            items = Markup("").join(
                Markup("<li>%s: %s</li>") % (account.display_name, ", ".join(reasons))
                for account, reasons in accounts.items()
            )
            wizard.monetary_review_warning = Markup("<p>%s</p><ul class='mb-0'>%s</ul>") % (
                _(
                    "These non-monetary accounts look monetary, e.g. receivables or payables in pesos, which"
                    " aren't restated. If they are, mark them as monetary; otherwise check \"Monetary"
                    " classification reviewed\" on the account:"
                ),
                items,
            )

    # Report data

    def _get_before_date_from(self):
        # Same date upstream adjusts the initial balance with
        return self.date_from + relativedelta(months=-1)

    def _get_adjustment_factors(self):
        """Return {origin month: (index, factor)} for the initial balance
        month and every period, as upstream computes them."""
        self.ensure_one()
        before_date_from = self._get_before_date_from()
        before_index = self.env["inflation.adjustment.index"].find(before_date_from)
        factors = {}
        if before_index:
            factors[before_date_from] = (before_index.value, self.end_index / before_index.value - 1.0)
        for period in self.get_periods():
            factors[period["date_from"]] = (period["index"].value, period["factor"])
        return factors

    def _get_adjustment_bases(self):
        """Return the amounts the adjustment applies to, as dicts with the
        account, origin month, date, entry (False for the aggregated initial
        balance), debit and credit."""
        self.ensure_one()
        AccountMoveLine = self.env["account.move.line"]
        domain = self.get_move_line_domain()
        before_date_from = self._get_before_date_from()
        bases = []
        initial_domain = domain + [("account_id.include_initial_balance", "=", True), ("date", "<", self.date_from)]
        for account, balance in AccountMoveLine._read_group(initial_domain, ["account_id"], ["balance:sum"]):
            bases.append({
                "account": account,
                "month": before_date_from,
                "date": self.date_from - timedelta(days=1),
                "move": False,
                "debit": max(balance, 0.0),
                "credit": max(-balance, 0.0),
            })
        if self._adjusts_openings_as_initial_balance():
            opening_domain = self._get_initial_balance_domain() + [("move_id", "in", self.opening_move_ids.ids)]
            for account, move, debit, credit in AccountMoveLine._read_group(
                opening_domain, ["account_id", "move_id"], ["debit:sum", "credit:sum"]
            ):
                bases.append({
                    "account": account, "month": before_date_from, "date": move.date, "move": move,
                    "debit": debit, "credit": credit,
                })
        for period in self.get_periods():
            period_domain = domain + [("date", ">=", period["date_from"]), ("date", "<=", period["date_to"])]
            for account, move, debit, credit in AccountMoveLine._read_group(
                period_domain, ["account_id", "move_id"], ["debit:sum", "credit:sum"]
            ):
                bases.append({
                    "account": account, "month": period["date_from"], "date": move.date, "move": move,
                    "debit": debit, "credit": credit,
                })
        return bases

    def _get_entry_adjustments(self, move):
        """Return ({(account id, origin month): adjustment}, total) of an
        adjustment entry, as plain values: they outlive a simulated entry."""
        self.ensure_one()
        adjustments = defaultdict(float)
        total = 0.0
        for line in move.line_ids:
            # Upstream's and this module's total lines on the adjustment account
            if line.account_id == self.account_id and line.date_maturity == self.date_to:
                total += line.balance
            else:
                adjustments[(line.account_id.id, line.date_maturity)] += line.balance
        return dict(adjustments), total

    def _simulate_entry_adjustments(self):
        """Create the adjustment entry as confirm() would, read it, and roll
        everything back: the report matches the entry to the cent without
        duplicating upstream's calculation."""
        self.ensure_one()
        result = ({}, 0.0)
        try:
            with self.env.cr.savepoint():
                action = self.with_context(inflation_adjustment_simulation=True).confirm()
                result = self._get_entry_adjustments(self.env["account.move"].browse(action["res_id"]))
                raise _SimulationRollback()
        except _SimulationRollback:
            pass
        return result

    def _get_adjustment_report_data(self, move=None):
        """Return the data of the adjustment detail report, from the given
        adjustment entry or else from a simulated one."""
        self.ensure_one()
        if move:
            adjustments, total = self._get_entry_adjustments(move)
        else:
            vals = self._get_hidden_fields_values()
            if vals:
                self.write(vals)
            adjustments, total = self._simulate_entry_adjustments()
        currency = self.company_id.currency_id
        factors = self._get_adjustment_factors()
        before_date_from = self._get_before_date_from()

        by_account = defaultdict(list)
        for base in self._get_adjustment_bases():
            if not (currency.is_zero(base["debit"]) and currency.is_zero(base["credit"])):
                by_account[base["account"]].append(base)
        for account_id, _month in adjustments:
            by_account[self.env["account.account"].browse(account_id)]

        accounts = []
        for account in sorted(by_account, key=lambda a: a.code or ""):
            bases = by_account[account]
            months = {}
            entries = []
            for base in sorted(bases, key=lambda b: (b["month"], b["date"], b["move"].name if b["move"] else "")):
                index, factor = factors.get(base["month"], (0.0, 0.0))
                month = months.setdefault(base["month"], {
                    "month": base["month"],
                    "label": _("Initial balance") if base["month"] == before_date_from
                    else base["month"].strftime("%m/%Y"),
                    "index": index, "factor": factor, "debit": 0.0, "credit": 0.0,
                    "adjustment": adjustments.get((account.id, base["month"]), 0.0),
                })
                month["debit"] += base["debit"]
                month["credit"] += base["credit"]
                entries.append({
                    "date": base["date"],
                    "name": base["move"].name if base["move"] else _("Initial balance"),
                    "index": index, "factor": factor,
                    "debit": base["debit"], "credit": base["credit"],
                    "adjustment_debit": currency.round(base["debit"] * factor),
                    "adjustment_credit": currency.round(base["credit"] * factor),
                })
            adjustment = sum(value for (account_id, _month), value in adjustments.items() if account_id == account.id)
            balance = sum(base["debit"] - base["credit"] for base in bases)
            entries_adjustment = sum(e["adjustment_debit"] - e["adjustment_credit"] for e in entries)
            accounts.append({
                "account": account,
                "months": list(months.values()),
                "entries": entries,
                "debit": sum(base["debit"] for base in bases),
                "credit": sum(base["credit"] for base in bases),
                "adjustment_debit": sum(e["adjustment_debit"] for e in entries),
                "adjustment_credit": sum(e["adjustment_credit"] for e in entries),
                "months_adjustment_debit": sum(max(m["adjustment"], 0.0) for m in months.values()),
                "months_adjustment_credit": sum(max(-m["adjustment"], 0.0) for m in months.values()),
                "rounding": currency.round(adjustment - entries_adjustment),
                "balance": balance,
                "adjustment": adjustment,
                "restated": balance + adjustment,
            })

        warnings = [warning for warning in (self.adjustment_warning,) if warning]
        return {
            "company": self.company_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "end_index": self.end_index,
            "move_name": move.name if move else False,
            "generated_at": fields.Datetime.context_timestamp(self, fields.Datetime.now()),
            "accounts": accounts,
            "total_adjustment": sum(account["adjustment"] for account in accounts),
            "recpam": total,
            "warnings": warnings,
            "review_accounts": self._get_monetary_review_accounts(),
            "entries_info": self._get_report_entries_info(),
        }

    def _get_report_entries_info(self):
        """Return [(label, entry names)] of the closing/opening entries the
        adjustment was computed with, so the report documents them."""
        self.ensure_one()

        def names(moves):
            return ", ".join(moves.sorted(lambda m: (m.date, m.name)).mapped("name"))

        if self._excludes_closing_opening_entries():
            return [
                (_("Closing entries excluded"), names(self.closing_move_ids)),
                (_("Opening entries excluded"), names(self.opening_move_ids)),
            ]
        if self._adjusts_openings_as_initial_balance():
            return [(
                _("Opening entries adjusted as initial balance (first fiscal year in Odoo)"),
                names(self.opening_move_ids),
            )]
        return [(_("Closing/opening entries"), _("None indicated"))]

    # Files

    def _get_report_filename(self):
        return _(
            "Inflation adjustment detail %(date_from)s - %(date_to)s",
            date_from=self.date_from.strftime("%d-%m-%Y"),
            date_to=self.date_to.strftime("%d-%m-%Y"),
        )

    def _render_report_pdf(self, move=None):
        data = {"detail": self.report_detail}
        if move:
            data["move_id"] = move.id
        content, _report_type = self.env["ir.actions.report"]._render_qweb_pdf(REPORT, self.ids, data=data)
        return content

    def _render_report_xlsx(self, report):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        bold = workbook.add_format({"bold": True})
        title = workbook.add_format({"bold": True, "font_size": 14})
        header = workbook.add_format({"bold": True, "bottom": 1, "text_wrap": True, "valign": "top"})
        money = workbook.add_format({"num_format": "#,##0.00"})
        money_bold = workbook.add_format({"num_format": "#,##0.00", "bold": True, "top": 1})
        factor = workbook.add_format({"num_format": "0.0000"})
        percent = workbook.add_format({"num_format": "0.00%"})
        index = workbook.add_format({"num_format": "#,##0.0000"})
        date = workbook.add_format({"num_format": "dd/mm/yyyy"})

        def write_header(sheet, columns, row):
            for col, (label, width) in enumerate(columns):
                sheet.write(row, col, label, header)
                sheet.set_column(col, col, width)
            sheet.freeze_panes(row + 1, 0)
            return row + 1

        company = report["company"]
        summary = workbook.add_worksheet(_("Summary"))
        summary.write(0, 0, _("Inflation adjustment detail"), title)
        info = [
            (_("Company"), company.name),
            (_("Tax ID"), company.vat or ""),
            (_("Period"), "%s - %s" % (format_date(self.env, report["date_from"]), format_date(self.env, report["date_to"]))),
            (_("Entry"), report["move_name"] or _("Simulation (no entry created)")),
            (_("Generated on"), report["generated_at"].strftime("%d/%m/%Y %H:%M")),
        ] + report["entries_info"]
        for row, (label, value) in enumerate(info, start=2):
            summary.write(row, 0, label, bold)
            summary.write(row, 1, value)
        row = len(info) + 3
        for text in report["warnings"]:
            summary.write(row, 0, _("Warning"), bold)
            summary.write(row, 1, Markup(text).striptags())
            row += 1
        row = write_header(summary, [
            (_("Code"), 14), (_("Account"), 45), (_("Historical balance"), 18), (_("Adjustment"), 18),
            (_("Restated balance"), 18),
        ], row + 1)
        for account in report["accounts"]:
            summary.write(row, 0, account["account"].code)
            summary.write(row, 1, account["account"].name)
            summary.write_number(row, 2, account["balance"], money)
            summary.write_number(row, 3, account["adjustment"], money)
            summary.write_number(row, 4, account["restated"], money)
            row += 1
        summary.write(row, 1, _("Total adjustment"), bold)
        summary.write_number(row, 3, report["total_adjustment"], money_bold)
        summary.write(row + 1, 1, _("Adjustment account total"), bold)
        summary.write_number(row + 1, 3, report["recpam"], money_bold)

        by_month = workbook.add_worksheet(_("By month"))
        row = write_header(by_month, [
            (_("Code"), 14), (_("Account"), 40), (_("Origin month"), 14), (_("Index"), 12), (_("Coefficient"), 11),
            (_("%"), 9), (_("Debit"), 16), (_("Credit"), 16), (_("Adjustment debit"), 16), (_("Adjustment credit"), 16),
        ], 0)
        for account in report["accounts"]:
            for month in account["months"]:
                by_month.write(row, 0, account["account"].code)
                by_month.write(row, 1, account["account"].name)
                by_month.write(row, 2, month["label"])
                by_month.write_number(row, 3, month["index"], index)
                by_month.write_number(row, 4, 1.0 + month["factor"], factor)
                by_month.write_number(row, 5, month["factor"], percent)
                by_month.write_number(row, 6, month["debit"], money)
                by_month.write_number(row, 7, month["credit"], money)
                by_month.write_number(row, 8, max(month["adjustment"], 0.0), money)
                by_month.write_number(row, 9, max(-month["adjustment"], 0.0), money)
                row += 1

        by_entry = workbook.add_worksheet(_("By entry"))
        row = write_header(by_entry, [
            (_("Code"), 14), (_("Account"), 40), (_("Date"), 12), (_("Entry"), 24), (_("Index"), 12),
            (_("Coefficient"), 11), (_("%"), 9), (_("Debit"), 16), (_("Adjustment debit"), 16), (_("Credit"), 16),
            (_("Adjustment credit"), 16),
        ], 0)
        for account in report["accounts"]:
            for entry in account["entries"]:
                by_entry.write(row, 0, account["account"].code)
                by_entry.write(row, 1, account["account"].name)
                by_entry.write_datetime(row, 2, fields.Datetime.to_datetime(entry["date"]), date)
                by_entry.write(row, 3, entry["name"])
                by_entry.write_number(row, 4, entry["index"], index)
                by_entry.write_number(row, 5, 1.0 + entry["factor"], factor)
                by_entry.write_number(row, 6, entry["factor"], percent)
                by_entry.write_number(row, 7, entry["debit"], money)
                by_entry.write_number(row, 8, entry["adjustment_debit"], money)
                by_entry.write_number(row, 9, entry["credit"], money)
                by_entry.write_number(row, 10, entry["adjustment_credit"], money)
                row += 1
            if account["rounding"]:
                by_entry.write(row, 0, account["account"].code)
                by_entry.write(row, 1, account["account"].name)
                by_entry.write(row, 3, _("Rounding difference"))
                by_entry.write_number(row, 8 if account["rounding"] > 0 else 10, abs(account["rounding"]), money)
                row += 1

        review = workbook.add_worksheet(_("Accounts to review"))
        row = write_header(review, [(_("Code"), 14), (_("Account"), 45), (_("Why it looks monetary"), 60)], 0)
        for account, reasons in report["review_accounts"].items():
            review.write(row, 0, account.code)
            review.write(row, 1, account.name)
            review.write(row, 2, ", ".join(reasons))
            row += 1

        workbook.close()
        return output.getvalue()

    def _download_file(self, name, content, mimetype):
        attachment = self.env["ir.attachment"].create({
            "name": name,
            "raw": content,
            "mimetype": mimetype,
            "res_model": self._name,
            "res_id": self.id,
        })
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "download"}

    def action_simulate_pdf(self):
        self.ensure_one()
        return self._download_file(
            _("%(name)s (simulation).pdf", name=self._get_report_filename()), self._render_report_pdf(), "application/pdf"
        )

    def action_simulate_xlsx(self):
        self.ensure_one()
        content = self._render_report_xlsx(self._get_adjustment_report_data())
        return self._download_file(_("%(name)s (simulation).xlsx", name=self._get_report_filename()), content, XLSX_MIMETYPE)

    def _attach_report_files(self, move):
        """Attach the detail report, PDF and Excel, to the adjustment entry."""
        self.ensure_one()
        name = self._get_report_filename()
        attachments = self.env["ir.attachment"].create([
            {
                "name": f"{name}.pdf",
                "raw": self._render_report_pdf(move),
                "mimetype": "application/pdf",
                "res_model": "account.move",
                "res_id": move.id,
            },
            {
                "name": f"{name}.xlsx",
                "raw": self._render_report_xlsx(self._get_adjustment_report_data(move)),
                "mimetype": XLSX_MIMETYPE,
                "res_model": "account.move",
                "res_id": move.id,
            },
        ])
        move.message_post(body=_("Inflation adjustment detail report."), attachment_ids=attachments.ids)

    def confirm(self):
        action = super().confirm()
        if not self.env.context.get("inflation_adjustment_simulation"):
            self._attach_report_files(self.env["account.move"].browse(action["res_id"]))
        return action


class ReportInflationAdjustment(models.AbstractModel):
    _name = "report.l10n_ar_inflation_adjustment_improvements.report_axi"
    _description = "Inflation adjustment detail report"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        wizard = self.env["inflation.adjustment"].browse(docids)
        move = self.env["account.move"].browse(data["move_id"]) if data.get("move_id") else None
        env = self.env

        def amount(value):
            return formatLang(env, value, digits=2)

        return {
            "doc_ids": docids,
            "docs": wizard,
            "report": wizard._get_adjustment_report_data(move),
            "detail": data.get("detail") or wizard.report_detail,
            "amount": amount,
            "coefficient": lambda factor: formatLang(env, 1.0 + factor, digits=4),
            "percent": lambda factor: formatLang(env, factor * 100.0, digits=2) + "%",
            "index": lambda value: formatLang(env, value, digits=2),
            "fdate": lambda value: format_date(env, value),
        }
