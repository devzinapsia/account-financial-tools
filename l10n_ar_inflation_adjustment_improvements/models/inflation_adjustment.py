from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools.misc import format_date, formatLang


class InflationAdjustment(models.TransientModel):
    _inherit = "inflation.adjustment"

    first_odoo_fiscal_year = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is this the first fiscal year recorded in Odoo?",
        default="no",
        help="Answer yes if Odoo has no closing entry of the previous fiscal year, e.g. because the"
        " company started using Odoo this fiscal year: the opening entries are then adjusted as"
        " initial balances, instead of being excluded together with the closing entries.",
    )
    closing_move_ids = fields.Many2many(
        "account.move",
        relation="inflation_adjustment_closing_move_rel",
        column1="wizard_id",
        column2="move_id",
        string="Previous fiscal year closing entries",
        domain="[('state', '=', 'posted'), ('company_id', '=', company_id), ('date', '<', date_from)]",
    )
    opening_move_ids = fields.Many2many(
        "account.move",
        relation="inflation_adjustment_opening_move_rel",
        column1="wizard_id",
        column2="move_id",
        string="Opening entries",
        domain="[('state', '=', 'posted'), ('company_id', '=', company_id),"
        " ('date', '>=', date_from), ('date', '<=', date_to)]",
    )
    adjustment_warning = fields.Html(
        string="Adjustment warning",
        compute="_compute_adjustment_warning",
        sanitize=False,
    )

    def _excludes_closing_opening_entries(self):
        """Regular fiscal year: the closing and opening entries cancel each
        other out, so both are excluded (upstream logic, on several entries)."""
        self.ensure_one()
        return self.open_cloure_entry == "yes" and self.first_odoo_fiscal_year != "yes"

    def _adjusts_openings_as_initial_balance(self):
        """First fiscal year in Odoo: there is no closing entry, and no history
        for it to cancel out, so the balances only live in the opening entries."""
        self.ensure_one()
        return self.open_cloure_entry == "yes" and self.first_odoo_fiscal_year == "yes"

    def _get_initial_balance_domain(self):
        """Move lines that make up the initial balance upstream (non-monetary
        accounts carrying their balance forward)."""
        self.ensure_one()
        return [
            ("account_id.is_monetary", "=", False),
            ("account_id.include_initial_balance", "=", True),
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),
        ]

    def _get_balances_by_account(self, domain):
        return dict(self.env["account.move.line"]._read_group(domain, ["account_id"], ["balance:sum"]))

    @api.depends(
        "open_cloure_entry", "first_odoo_fiscal_year", "closing_move_ids", "opening_move_ids",
        "company_id", "date_from", "date_to", "journal_id", "account_id",
    )
    def _compute_adjustment_warning(self):
        for wizard in self:
            warnings = [w for w in (wizard._get_existing_adjustment_warning(), wizard._get_adjustment_warning()) if w]
            wizard.adjustment_warning = Markup("").join(warnings) if warnings else False

    def _get_existing_adjustment_moves(self):
        """Posted inflation adjustment entries already recorded within the
        period, e.g. by a previous run of this wizard."""
        self.ensure_one()
        if not (self.journal_id and self.account_id and self.date_from and self.date_to):
            return self.env["account.move"]
        return self.env["account.move"].search([
            ("journal_id", "=", self.journal_id.id),
            ("state", "=", "posted"),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
            ("line_ids.account_id", "=", self.account_id.id),
        ])

    def _get_existing_adjustment_warning(self):
        moves = self._get_existing_adjustment_moves()
        if not moves:
            return False
        return Markup("<p>%s</p>") % _(
            "There are posted inflation adjustment entries within this period: %(entries)s. Their lines count as"
            " movements of the period, and confirming again would record the adjustment twice: if you are"
            " recalculating it, reset them to draft or cancel them first.",
            entries=", ".join(moves.mapped("name")),
        )

    def _get_adjustment_warning(self):
        self.ensure_one()
        closings = self.closing_move_ids._origin
        openings = self.opening_move_ids._origin
        if not (self.company_id and self.date_from and openings):
            return False
        currency = self.company_id.currency_id
        domain = self._get_initial_balance_domain()
        if self._excludes_closing_opening_entries():
            if not closings:
                return False
            # Excluding both only works if they cancel each other out
            differences = self._get_balances_by_account(domain + [("move_id", "in", (closings + openings).ids)])
            message = _(
                "The selected closing and opening entries don't cancel each other out in these accounts,"
                " so their initial balance may be wrong. Check that no entry is missing or selected by mistake:"
            )
        elif self._adjusts_openings_as_initial_balance():
            prior = self._get_balances_by_account(domain + [("date", "<", self.date_from)])
            opened = self._get_balances_by_account(domain + [("move_id", "in", openings.ids)])
            # A prior balance cancelled by the opening entries (e.g. a bridge
            # account used to load the pending invoices) is fine
            differences = {
                account: balance
                for account, balance in prior.items()
                if not currency.is_zero(balance + opened.get(account, 0.0))
            }
            message = _(
                "Besides the opening entries, these balances prior to the start date will also count as"
                " initial balance. If this isn't the first fiscal year recorded in Odoo, answer no and"
                " select the previous fiscal year closing entries:"
            )
        else:
            return False
        differences = {account: balance for account, balance in differences.items() if not currency.is_zero(balance)}
        if not differences:
            return False
        items = Markup("").join(
            Markup("<li>%s: %s</li>") % (account.display_name, formatLang(self.env, balance, currency_obj=currency))
            for account, balance in sorted(differences.items(), key=lambda item: item[0].code or "")
        )
        return Markup("<p>%s</p><ul class='mb-0'>%s</ul>") % (message, items)

    def _get_hidden_fields_values(self):
        """Return the values that reset the fields hidden by the current
        answers, so they can't leak into the move line domain."""
        self.ensure_one()
        vals = {}
        # Replaced by the closing/opening entries lists
        if self.closure_move_id:
            vals["closure_move_id"] = False
        if self.open_move_id:
            vals["open_move_id"] = False
        if self.open_cloure_entry != "yes" and self.opening_move_ids:
            vals["opening_move_ids"] = [Command.clear()]
        if not self._excludes_closing_opening_entries() and self.closing_move_ids:
            vals["closing_move_ids"] = [Command.clear()]
        return vals

    @api.onchange("open_cloure_entry", "first_odoo_fiscal_year")
    def _onchange_closing_opening_answers(self):
        for wizard in self:
            wizard.update(wizard._get_hidden_fields_values())

    @api.constrains("open_cloure_entry", "first_odoo_fiscal_year", "closing_move_ids", "opening_move_ids")
    def _check_closing_opening_entries(self):
        for wizard in self.filtered(lambda w: w.open_cloure_entry == "yes"):
            if not wizard.opening_move_ids:
                raise ValidationError(_("Please select the opening entries."))
            if wizard._excludes_closing_opening_entries() and not wizard.closing_move_ids:
                raise ValidationError(
                    _(
                        "Please select the previous fiscal year closing entries. If there are none because"
                        " this is the first fiscal year recorded in Odoo, answer yes to that question."
                    )
                )

    @api.constrains("closing_move_ids", "opening_move_ids", "date_from", "date_to")
    def _check_closing_opening_entries_dates(self):
        for wizard in self:
            if wizard.closing_move_ids.filtered(lambda move: move.date >= wizard.date_from):
                raise ValidationError(
                    _(
                        "The closing entries must be the previous fiscal year's ones, dated before the"
                        " start date (%(date)s).",
                        date=format_date(self.env, wizard.date_from),
                    )
                )
            if wizard.opening_move_ids.filtered(lambda move: not wizard.date_from <= move.date <= wizard.date_to):
                raise ValidationError(
                    _(
                        "The opening entries must be dated within the adjusted period (%(date_from)s - %(date_to)s).",
                        date_from=format_date(self.env, wizard.date_from),
                        date_to=format_date(self.env, wizard.date_to),
                    )
                )

    def get_move_line_domain(self):
        res = super().get_move_line_domain()
        if self._excludes_closing_opening_entries():
            excluded_moves = self.closing_move_ids + self.opening_move_ids
        elif self._adjusts_openings_as_initial_balance():
            # Left out of their month: _get_opening_entries_adjustment_lines()
            # adjusts them as initial balance instead
            excluded_moves = self.opening_move_ids
        else:
            excluded_moves = self.env["account.move"]
        if excluded_moves:
            res += [("move_id", "not in", excluded_moves.ids)]
        return res

    def _get_opening_entries_adjustment_lines(self):
        """Adjustment lines for the opening entries as initial balance, the
        same way upstream adjusts the balances prior to the start date: with
        the index of the month before it."""
        self.ensure_one()
        before_date_from = self.date_from + relativedelta(months=-1)
        before_index = self.env["inflation.adjustment.index"].find(before_date_from)
        if not before_index:
            raise UserError(
                _(
                    "No inflation adjustment index was found for the previous date (%(date)s)."
                    " Please configure the corresponding index.",
                    date=format_date(self.env, before_date_from),
                )
            )
        factor = (self.end_index / before_index.value) - 1.0
        currency = self.company_id.currency_id
        balances = self._get_balances_by_account(
            self._get_initial_balance_domain() + [("move_id", "in", self.opening_move_ids.ids)]
        )
        lines = []
        for account, balance in balances.items():
            adjustment = currency.round(balance * factor)
            if currency.is_zero(adjustment):
                continue
            lines.append({
                "account_id": account.id,
                "name": _(
                    "Inflation adjustment opening entries (%(amount)s * %(factor).2f%%)",
                    amount=formatLang(self.env, balance, currency_obj=currency),
                    factor=factor * 100.0,
                ),
                "date_maturity": before_date_from,
                "balance": adjustment,
            })
        if lines:
            total = sum(line["balance"] for line in lines)
            lines.append({
                "account_id": self.account_id.id,
                "name": _(
                    "Global inflation adjustment opening entries [%(date_from)s] / [%(date_to)s]",
                    date_from=self.date_from,
                    date_to=self.date_to,
                ),
                "date_maturity": self.date_to,
                "balance": -total,
            })
        for line in lines:
            balance = line.pop("balance")
            line["debit" if balance > 0 else "credit"] = abs(balance)
        return lines

    def confirm(self):
        self.ensure_one()
        vals = self._get_hidden_fields_values()
        if vals:
            # Same cleanup as the onchange, for wizards not filled in through the form
            self.write(vals)
        if not self._adjusts_openings_as_initial_balance():
            return super().confirm()
        opening_lines = self._get_opening_entries_adjustment_lines()
        if not opening_lines:
            return super().confirm()
        # Raise a missing index of the period now, so that the only error
        # super() can still raise below is that there is nothing else to adjust
        self.get_periods()
        Move = self.env["account.move"].with_context(skip_invoice_sync=True)
        try:
            action = super().confirm()
        except UserError:
            # Only the opening entries to adjust (e.g. no other movement on
            # non-monetary accounts yet)
            move = Move.create({
                "journal_id": self.journal_id.id,
                "date": self.date_to,
                "ref": _("Inflation adjustment %(year)s", year=self.date_to.year),
                "line_ids": [Command.create(line) for line in opening_lines],
            })
            return move._get_access_action()
        Move.browse(action["res_id"]).write({"line_ids": [Command.create(line) for line in opening_lines]})
        return action
