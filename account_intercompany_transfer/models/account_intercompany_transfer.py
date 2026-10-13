from contextlib import contextmanager
from contextvars import ContextVar

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

SEQUENCE_CODE = "account.intercompany.transfer"

# Set only by this module's own server-side flows (the wizard and the
# cancellation). Unlike a context key, it can't be sent through RPC, so it
# can't be used to create transfers or change their data by hand.
_internal_write = ContextVar("account_intercompany_transfer_internal_write", default=False)


@contextmanager
def internal_write():
    token = _internal_write.set(True)
    try:
        yield
    finally:
        _internal_write.reset(token)


def is_internal_write():
    return _internal_write.get()


def journal_currency(journal):
    """Effective currency of a journal: its own, or its company's."""
    return journal.currency_id or journal.company_id.currency_id


class AccountIntercompanyTransfer(models.Model):
    _name = "account.intercompany.transfer"
    _description = "Intercompany transfer"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    # Every field but the memo is written once, by the wizard.
    _USER_WRITABLE_FIELDS = {"memo"}

    name = fields.Char(string="Number", readonly=True, copy=False, index="trigram")
    company_id = fields.Many2one(
        "res.company",
        string="Origin company",
        required=True,
        readonly=True,
        index=True,
    )
    date = fields.Date(required=True, readonly=True)
    amount = fields.Monetary(currency_field="currency_id", required=True, readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True, readonly=True)
    origin_journal_id = fields.Many2one(
        "account.journal",
        string="Origin journal",
        required=True,
        readonly=True,
    )
    destination_company_id = fields.Many2one(
        "res.company",
        string="Destination company",
        required=True,
        readonly=True,
        index=True,
    )
    destination_journal_id = fields.Many2one(
        "account.journal",
        string="Destination journal",
        required=True,
        readonly=True,
    )
    memo = fields.Char(tracking=True)
    state = fields.Selection(
        [("posted", "Posted"), ("cancelled", "Cancelled")],
        string="Status",
        required=True,
        default="posted",
        readonly=True,
        tracking=True,
        copy=False,
    )
    origin_payment_id = fields.Many2one(
        "account.payment",
        string="Origin payment",
        readonly=True,
        copy=False,
    )
    destination_payment_id = fields.Many2one(
        "account.payment",
        string="Destination payment",
        readonly=True,
        copy=False,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Transferred by",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains(
        "company_id",
        "destination_company_id",
        "origin_journal_id",
        "destination_journal_id",
        "currency_id",
        "amount",
    )
    def _check_transfer(self):
        for transfer in self:
            transfer._validate_transfer_values(
                transfer.origin_journal_id,
                transfer.destination_journal_id,
                transfer.amount,
                company=transfer.company_id,
                destination_company=transfer.destination_company_id,
                currency=transfer.currency_id,
            )

    @api.model
    def _validate_transfer_values(
        self,
        origin_journal,
        destination_journal,
        amount,
        company=None,
        destination_company=None,
        currency=None,
    ):
        """Business rules of a transfer, shared by the document constraint
        and the wizard. ``company``/``destination_company`` default to the
        companies of the journals; ``currency`` to the origin's currency.
        """
        company = company or origin_journal.company_id
        destination_company = destination_company or destination_journal.company_id
        if company == destination_company:
            raise ValidationError(_("The origin and destination companies must be different."))
        for journal, journal_company in (
            (origin_journal, company),
            (destination_journal, destination_company),
        ):
            if journal.company_id != journal_company:
                raise ValidationError(
                    _(
                        "The journal %(journal)s does not belong to %(company)s.",
                        journal=journal.display_name,
                        company=journal_company.display_name,
                    )
                )
            if journal.type not in ("bank", "cash"):
                raise ValidationError(
                    _(
                        "The journal %(journal)s must be a bank or cash journal.",
                        journal=journal.display_name,
                    )
                )
        for journal_company in company | destination_company:
            if not journal_company.intercompany_transfer_account_id:
                raise ValidationError(
                    _(
                        "%(company)s has no intercompany transfer bridge account. "
                        "Set it in the accounting settings of that company.",
                        company=journal_company.display_name,
                    )
                )
        origin_currency = journal_currency(origin_journal)
        destination_currency = journal_currency(destination_journal)
        if origin_currency != destination_currency:
            raise ValidationError(
                _(
                    "The origin journal %(origin)s is in %(origin_currency)s and the destination "
                    "journal %(destination)s is in %(destination_currency)s. Intercompany transfers "
                    "require both journals in the same currency.",
                    origin=origin_journal.display_name,
                    origin_currency=origin_currency.name,
                    destination=destination_journal.display_name,
                    destination_currency=destination_currency.name,
                )
            )
        if currency and currency != origin_currency:
            raise ValidationError(_("The currency of the transfer must be the currency of its journals."))
        if origin_currency.compare_amounts(amount, 0.0) <= 0:
            raise ValidationError(_("The amount of the transfer must be greater than zero."))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal_write():
            raise UserError(_("Intercompany transfers can only be created from the transfer wizard."))
        for vals in vals_list:
            company = self.env["res.company"].browse(vals["company_id"])
            vals["name"] = self._next_number(company, vals.get("date"))
        return super().create(vals_list)

    def write(self, vals):
        writable = self._get_user_writable_fields()
        protected = [self._fields[name].string for name in vals if name in self._fields and name not in writable]
        if protected and not is_internal_write():
            raise UserError(
                _(
                    "Only the memo of an intercompany transfer can be changed. "
                    "Cancel it and create a new one instead. Fields: %(fields)s",
                    fields=", ".join(protected),
                )
            )
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Intercompany transfers can't be deleted. Cancel them instead."))

    def _get_user_writable_fields(self):
        """Business fields stay locked; chatter/activity fields of the mail
        mixins remain writable so following, messages and activities work.
        """
        mixin_fields = set(self.env["mail.thread"]._fields) | set(self.env["mail.activity.mixin"]._fields)
        return self._USER_WRITABLE_FIELDS | mixin_fields

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    @api.model
    def _check_transfer_access(self, companies):
        """Server-side access check, whatever the UI showed: the user needs
        the module group and every company of the transfer among their
        allowed companies (ticking them in the switcher is not required).
        """
        if not self.env.user.has_group("account_intercompany_transfer.group_intercompany_transfer_user"):
            raise AccessError(_("You are not allowed to make intercompany transfers."))
        missing = companies - self.env.user.company_ids
        if missing:
            # The names of companies the user isn't allowed in can't be read.
            raise AccessError(
                _("Both companies of an intercompany transfer must be among your allowed companies.")
            )

    @api.model
    def _transfer_env(self, companies):
        """Environment where both companies are active for the current user.

        Core validates allowed_company_ids against the user's companies (an
        AccessError otherwise): no sudo, the user's access rights and record
        rules apply in both companies.
        """
        return self.env(context=dict(self.env.context, allowed_company_ids=companies.ids))

    @api.model
    def _check_lock_dates(self, companies, date):
        """Block a date inside a closed period of either company. Odoo would
        otherwise move that company's entry to its first open date, leaving
        both sides of the transfer on different dates.
        """
        for company in companies:
            violations = company._get_lock_date_violations(
                fields.Date.to_date(date),
                fiscalyear=True,
                sale=False,
                purchase=False,
                tax=False,
                hard=True,
            )
            if violations:
                raise UserError(
                    _(
                        "The date %(date)s is in a closed period of %(company)s (%(lock_dates)s).",
                        date=fields.Date.to_string(fields.Date.to_date(date)),
                        company=company.display_name,
                        lock_dates=self.env["res.company"]._format_lock_dates(violations),
                    )
                )

    @api.model
    def _get_transfer_payment_method_line(self, journal, payment_type):
        line = journal._get_available_payment_method_lines(payment_type).filtered(
            lambda line: line.payment_method_id.code == "manual"
        )[:1]
        if not line:
            raise UserError(
                _(
                    "The journal %(journal)s has no manual payment method to %(direction)s money.",
                    journal=journal.display_name,
                    direction=_("send") if payment_type == "outbound" else _("receive"),
                )
            )
        if not line.payment_account_id:
            raise UserError(
                _(
                    "The payment method %(method)s of the journal %(journal)s has no outstanding account. "
                    "Set it on the journal, in the incoming/outgoing payments tab.",
                    method=line.name,
                    journal=journal.display_name,
                )
            )
        return line

    @api.model
    def _create_transfer(self, origin_journal, destination_journal, amount, date, memo=False, destination_company=None):
        """Create a transfer and its two posted payments, in one transaction:
        any error in either company leaves nothing behind.

        Private on purpose (not callable through RPC): it is the only entry
        point allowed to create transfers, and it re-validates everything.
        """
        self._check_transfer_access(self.env["res.company"])
        # Read the journals as the user, with all their companies active:
        # a journal of a company they aren't allowed in is not found.
        user_env = self._transfer_env(self.env.user.company_ids)
        journals = user_env["account.journal"].search([("id", "in", (origin_journal | destination_journal).ids)])
        if len(journals) != len((origin_journal | destination_journal).ids):
            raise AccessError(_("You are not allowed to use the selected journals."))
        company = origin_journal.with_env(user_env).company_id
        journal_destination_company = destination_journal.with_env(user_env).company_id
        self._check_transfer_access(company | journal_destination_company | (destination_company or company))
        env = self._transfer_env(company | journal_destination_company)
        origin_journal = origin_journal.with_env(env)
        destination_journal = destination_journal.with_env(env)
        # The destination company picked in the wizard must be the one of
        # the destination journal.
        destination_company = (destination_company or journal_destination_company).with_env(user_env)
        self._validate_transfer_values(
            origin_journal,
            destination_journal,
            amount,
            destination_company=destination_company,
        )
        self._check_lock_dates(company | destination_company, date)
        currency = journal_currency(origin_journal)
        origin_method = self._get_transfer_payment_method_line(origin_journal, "outbound")
        destination_method = self._get_transfer_payment_method_line(destination_journal, "inbound")

        Transfer = env[self._name].with_company(company)
        with internal_write():
            transfer = Transfer.create(
                {
                    "company_id": company.id,
                    "destination_company_id": destination_company.id,
                    "origin_journal_id": origin_journal.id,
                    "destination_journal_id": destination_journal.id,
                    "amount": amount,
                    "currency_id": currency.id,
                    "date": date,
                    "memo": memo,
                }
            )
            payment_memo = f"{transfer.name} - {memo}" if memo else transfer.name
            payments = env["account.payment"]
            for journal, method, payment_type, partner_company in (
                (origin_journal, origin_method, "outbound", destination_company),
                (destination_journal, destination_method, "inbound", company),
            ):
                # partner_type is required by payments but meaningless here:
                # 'customer' keeps the outbound payment out of the
                # vendor-payment processes (authorization, review, withholdings).
                payments |= (
                    env["account.payment"]
                    .with_company(journal.company_id)
                    .create(
                        {
                            "payment_type": payment_type,
                            "partner_type": "customer",
                            "partner_id": partner_company.partner_id.id,
                            "company_id": journal.company_id.id,
                            "journal_id": journal.id,
                            "payment_method_line_id": method.id,
                            "currency_id": currency.id,
                            "amount": amount,
                            "date": date,
                            "memo": payment_memo,
                            "intercompany_transfer_id": transfer.id,
                        }
                    )
                )
            origin_payment, destination_payment = payments
            transfer.write(
                {
                    "origin_payment_id": origin_payment.id,
                    "destination_payment_id": destination_payment.id,
                }
            )
            origin_payment.with_company(company).action_post()
            destination_payment.with_company(destination_company).action_post()

        transfer.message_post(
            body=_(
                "Transfer posted: %(origin)s in %(company)s and %(destination)s in %(destination_company)s.",
                origin=origin_payment._get_html_link(),
                company=company.display_name,
                destination=destination_payment._get_html_link(),
                destination_company=destination_company.display_name,
            )
        )
        for payment in payments:
            payment.message_post(body=_("Created by the intercompany transfer %s.", transfer._get_html_link()))
        return transfer.with_env(self.env)

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def action_cancel(self):
        """Cancel both payments, in one transaction. A cancelled transfer
        can't be posted again: a new one is created instead.
        """
        for transfer in self:
            transfer._cancel_transfer()
        return True

    def _cancel_transfer(self):
        self.ensure_one()
        companies = self.company_id | self.destination_company_id
        self._check_transfer_access(companies)
        if self.state != "posted":
            raise UserError(_("Only posted intercompany transfers can be cancelled."))
        env = self._transfer_env(companies)
        transfer = self.with_env(env)
        payments = transfer.origin_payment_id | transfer.destination_payment_id
        for payment in payments:
            transfer._check_payment_cancellable(payment)
        with internal_write():
            for payment in payments:
                payment.with_company(payment.company_id).action_cancel()
            transfer.state = "cancelled"
        transfer.message_post(
            body=_(
                "Transfer cancelled: %(origin)s in %(company)s and %(destination)s in %(destination_company)s "
                "were cancelled.",
                origin=transfer.origin_payment_id._get_html_link(),
                company=transfer.company_id.display_name,
                destination=transfer.destination_payment_id._get_html_link(),
                destination_company=transfer.destination_company_id.display_name,
            )
        )

    def _check_payment_cancellable(self, payment):
        """A payment can't be cancelled once any of its journal items is
        reconciled (typically its outstanding line with a bank statement
        line), nor inside a closed period of its company.
        """
        for line in payment.move_id.line_ids:
            partials = line.matched_debit_ids | line.matched_credit_ids
            counterparts = (partials.debit_move_id | partials.credit_move_id) - line
            if not counterparts:
                continue
            statement_lines = counterparts.move_id.statement_line_id
            if statement_lines:
                reason = _(
                    "is reconciled with the bank statement line %(lines)s",
                    lines=", ".join(statement_lines.mapped("display_name")),
                )
            else:
                reason = _(
                    "has its journal item on %(account)s reconciled with %(entries)s",
                    account=line.account_id.display_name,
                    entries=", ".join(counterparts.move_id.mapped("display_name")),
                )
            raise UserError(
                _(
                    "The transfer %(transfer)s can't be cancelled: the payment %(payment)s of %(company)s "
                    "%(reason)s. Undo that reconciliation first.",
                    transfer=self.display_name,
                    payment=payment.display_name,
                    company=payment.company_id.display_name,
                    reason=reason,
                )
            )
        try:
            self._check_lock_dates(payment.company_id, payment.move_id.date or payment.date)
        except UserError as error:
            raise UserError(
                _(
                    "The transfer %(transfer)s can't be cancelled: the payment %(payment)s of %(company)s "
                    "is dated in a closed period. %(error)s",
                    transfer=self.display_name,
                    payment=payment.display_name,
                    company=payment.company_id.display_name,
                    error=error.args[0],
                )
            ) from error

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_origin_payment(self):
        return self._action_open_payment(self.origin_payment_id, self.company_id)

    def action_open_destination_payment(self):
        return self._action_open_payment(self.destination_payment_id, self.destination_company_id)

    def _action_open_payment(self, payment, company):
        self.ensure_one()
        # The web client only shows records of the companies ticked in the
        # switcher: say which one to tick instead of an access error.
        if company not in self.env.companies:
            raise UserError(
                _(
                    "This payment of %(transfer)s belongs to %(company)s. Select that company in the "
                    "company switcher to open it.",
                    transfer=self.display_name,
                    company=company.display_name,
                )
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "view_mode": "form",
            "res_id": payment.id,
        }

    @api.model
    def _next_number(self, company, date):
        number = (
            self.env["ir.sequence"]
            .with_company(company)
            .next_by_code(SEQUENCE_CODE, sequence_date=date or fields.Date.context_today(self))
        )
        if not number:
            raise UserError(
                _(
                    "%(company)s has no intercompany transfer sequence. Update the module "
                    "'Transferencias intercompany' to create it.",
                    company=company.display_name,
                )
            )
        return number
