from odoo import api, fields, models

from ..models.account_intercompany_transfer import journal_currency


class AccountIntercompanyTransferWizard(models.TransientModel):
    _name = "account.intercompany.transfer.wizard"
    _description = "Intercompany transfer wizard"

    # The pickers must offer journals and companies of every company the
    # user is allowed in, even those not ticked in the company switcher.
    # Their options are computed with all those companies active and handed
    # to the view as plain id domains: relational fields holding records of
    # an unticked company couldn't be read in the user's environment.
    # picker_company_ids is passed as allowed_company_ids to the pickers'
    # searches, for the same reason.
    picker_company_ids = fields.Json(string="Picker companies", compute="_compute_picker_company_ids")
    origin_journal_domain = fields.Binary(string="Origin journal domain", compute="_compute_origin_journal_domain")
    destination_company_domain = fields.Binary(
        string="Destination company domain", compute="_compute_destination_company_domain"
    )
    destination_journal_domain = fields.Binary(
        string="Destination journal domain", compute="_compute_destination_journal_domain"
    )

    origin_journal_id = fields.Many2one(
        "account.journal",
        string="Origin journal",
        required=True,
        domain="origin_journal_domain",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Origin company",
        compute="_compute_company_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        compute="_compute_currency_id",
    )
    destination_company_id = fields.Many2one(
        "res.company",
        string="Destination company",
        required=True,
        domain="destination_company_domain",
    )
    destination_journal_id = fields.Many2one(
        "account.journal",
        string="Destination journal",
        required=True,
        domain="destination_journal_domain",
    )
    amount = fields.Monetary(currency_field="currency_id", required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    memo = fields.Char()

    # ------------------------------------------------------------------
    # Options, computed as the user with all their companies active
    # ------------------------------------------------------------------

    def _get_user_companies_env(self):
        """The user's own environment with all their allowed companies
        active (core rejects companies the user isn't allowed in).
        """
        return self.env["account.intercompany.transfer"]._transfer_env(self.env.user.company_ids)

    def _get_bridge_companies(self):
        env = self._get_user_companies_env()
        return env.user.company_ids.filtered("intercompany_transfer_account_id")

    def _get_origin_journals(self):
        env = self._get_user_companies_env()
        return env["account.journal"].search(
            [
                ("type", "in", ("bank", "cash")),
                ("company_id", "in", self._get_bridge_companies().ids),
            ]
        )

    def _get_destination_companies(self):
        self.ensure_one()
        return self._get_bridge_companies().filtered(lambda company: company.id != self.company_id.id)

    def _get_destination_journals(self):
        self.ensure_one()
        if not self.destination_company_id or not self.origin_journal_id:
            return self.env["account.journal"]
        env = self._get_user_companies_env()
        journals = env["account.journal"].search(
            [
                ("type", "in", ("bank", "cash")),
                ("company_id", "=", self.destination_company_id.id),
            ]
        )
        currency = self.currency_id.with_env(env)
        return journals.filtered(lambda journal: journal_currency(journal) == currency)

    def _compute_picker_company_ids(self):
        for wizard in self:
            wizard.picker_company_ids = self.env.user.company_ids.ids

    def _compute_origin_journal_domain(self):
        journal_ids = self._get_origin_journals().ids
        for wizard in self:
            wizard.origin_journal_domain = [("id", "in", journal_ids)]

    @api.depends("origin_journal_id")
    def _compute_company_id(self):
        env = self._get_user_companies_env()
        for wizard in self:
            wizard.company_id = wizard.origin_journal_id.with_env(env).company_id.id

    @api.depends("origin_journal_id")
    def _compute_currency_id(self):
        env = self._get_user_companies_env()
        for wizard in self:
            journal = wizard.origin_journal_id.with_env(env)
            wizard.currency_id = journal_currency(journal).id if journal else self.env.company.currency_id

    @api.depends("company_id")
    def _compute_destination_company_domain(self):
        for wizard in self:
            wizard.destination_company_domain = [("id", "in", wizard._get_destination_companies().ids)]

    @api.depends("destination_company_id", "origin_journal_id")
    def _compute_destination_journal_domain(self):
        for wizard in self:
            wizard.destination_journal_domain = [("id", "in", wizard._get_destination_journals().ids)]

    @api.onchange("origin_journal_id")
    def _onchange_origin_journal_id(self):
        if self.destination_company_id.id not in self._get_destination_companies().ids:
            self.destination_company_id = False

    @api.onchange("destination_company_id", "origin_journal_id")
    def _onchange_destination_company_id(self):
        if self.destination_journal_id.id not in self._get_destination_journals().ids:
            self.destination_journal_id = False

    def action_confirm(self):
        """Everything is validated again on the server by _create_transfer:
        the view domains above are only a convenience.
        """
        self.ensure_one()
        transfer = self.env["account.intercompany.transfer"]._create_transfer(
            self.origin_journal_id,
            self.destination_journal_id,
            self.amount,
            self.date,
            self.memo,
            destination_company=self.destination_company_id,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.intercompany.transfer",
            "view_mode": "form",
            "res_id": transfer.id,
        }
