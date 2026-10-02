from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.account_vendor_bill_authorization.models.account_move import VENDOR_BILL_TYPES

from .res_company import PAY_NOW_JOURNAL_TYPES

PAY_NOW_VENDOR_GROUP_XMLID = "account_payment_pro.group_pay_now_vendor_invoices"


class AccountMove(models.Model):
    _inherit = "account.move"

    pay_now_available_journal_ids = fields.Many2many(
        "account.journal",
        compute="_compute_pay_now_available_journal_ids",
        string="Available pay now journals",
    )
    can_set_pay_now_journal = fields.Boolean(
        compute="_compute_can_set_pay_now_journal",
        string="Can set pay now journal",
    )

    @api.depends("company_id")
    def _compute_pay_now_available_journal_ids(self):
        # When the company configures journals that bypass authorization,
        # those are the only ones a vendor bill can be paid with on
        # confirmation; otherwise the pay now journal keeps working as
        # account_payment_pro defines it (the view keeps its own domain).
        journals_by_company = {}
        for move in self:
            company = move.company_id
            if company not in journals_by_company:
                bypass_journals = company.sudo().bypass_journal_ids
                journals_by_company[company] = bypass_journals or self.env["account.journal"].search(
                    [("company_id", "=", company.id), ("type", "in", PAY_NOW_JOURNAL_TYPES)]
                )
            move.pay_now_available_journal_ids = journals_by_company[company]

    @api.depends("company_id")
    @api.depends_context("uid")
    def _compute_can_set_pay_now_journal(self):
        for move in self:
            company = move.company_id.sudo()
            move.can_set_pay_now_journal = (
                not company.bypass_journal_ids or self.env.user in company.bypass_user_ids
            )

    @api.depends(
        "move_type",
        "company_id",
        "partner_id",
        "journal_id",
        "currency_id",
        "invoice_date",
        "date",
        "classification_id",
        "amount_total",
        "fiscal_position_id",
        "invoice_payment_term_id",
        # Added by this module; the list above repeats the base module's,
        # since an @api.depends on an override replaces the original one.
        "pay_now_journal_id",
    )
    def _compute_matched_policy_ids(self):
        super()._compute_matched_policy_ids()
        if not self._is_pay_now_vendor_enabled():
            return
        for move in self:
            if move.matched_policy_ids and move._is_authorization_bypassed():
                # "Always block" keeps absolute priority over the bypass:
                # only those policies stay matched, so the bill is still
                # blocked; every other policy is skipped.
                move.matched_policy_ids = move.matched_policy_ids.filtered("always_block")

    def _get_authorization_sensitive_fields(self):
        return super()._get_authorization_sensitive_fields() | {"pay_now_journal_id"}

    @api.model
    def _is_pay_now_vendor_enabled(self):
        """True when the "Allow pay now on vendor invoices?" setting of
        account_payment_pro is checked, read the same way that setting
        reads itself back (its group implied by every internal user).
        Without it this module is inert: the bypass never applies.
        """
        group = self.env.ref(PAY_NOW_VENDOR_GROUP_XMLID, raise_if_not_found=False)
        return bool(group) and group in self.env.ref("base.group_user").sudo().all_implied_ids

    def _is_authorization_bypassed(self):
        """True if this vendor bill is paid on confirmation with one of its
        company's journals that bypass authorization. Deliberately does not
        depend on the current user, since it drives stored computed fields:
        who may use the bypass is enforced separately, by
        _check_pay_now_journal_bypass_rights().
        """
        self.ensure_one()
        return bool(
            self.move_type in VENDOR_BILL_TYPES
            and self.pay_now_journal_id
            and self.pay_now_journal_id in self.company_id.sudo().bypass_journal_ids
        )

    def _check_pay_now_journal_bypass_rights(self):
        """While a company has journals that bypass authorization, only its
        allowed users can set a pay now journal on a vendor bill, or
        confirm a vendor bill that has one, and only with one of those
        journals.
        """
        if self.env.su or not self._is_pay_now_vendor_enabled():
            return
        for move in self:
            if move.move_type not in VENDOR_BILL_TYPES or not move.pay_now_journal_id:
                continue
            company = move.company_id.sudo()
            if not company.bypass_journal_ids:
                continue
            if self.env.user not in company.bypass_user_ids:
                raise UserError(
                    _(
                        "You are not allowed to use the pay now journal %(journal)s "
                        "on vendor bill %(bill)s: only the users allowed to bypass "
                        "vendor bill authorization can set a pay now journal or "
                        "confirm a vendor bill that has one.",
                        journal=move.pay_now_journal_id.display_name,
                        bill=move.display_name,
                    )
                )
            if move.pay_now_journal_id not in company.bypass_journal_ids:
                raise UserError(
                    _(
                        "The pay now journal %(journal)s of vendor bill %(bill)s is "
                        "not one of the journals that bypass authorization.",
                        journal=move.pay_now_journal_id.display_name,
                        bill=move.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves.filtered("pay_now_journal_id")._check_pay_now_journal_bypass_rights()
        return moves

    def write(self, vals):
        result = super().write(vals)
        if vals.get("pay_now_journal_id"):
            self._check_pay_now_journal_bypass_rights()
        return result

    def _check_vendor_bill_authorization_before_post(self):
        self.filtered(lambda m: m.state == "draft")._check_pay_now_journal_bypass_rights()
        return super()._check_vendor_bill_authorization_before_post()

    def action_post(self):
        bypassed = self.browse()
        if self._is_pay_now_vendor_enabled():
            bypassed = self.filtered(lambda m: m.state == "draft" and m._is_authorization_bypassed())
        result = super().action_post()
        for move in bypassed.filtered(lambda m: m.state == "posted"):
            move.message_post(
                body=_(
                    "Authorization not required: this vendor bill was paid on "
                    "confirmation with journal %s, which bypasses vendor bill "
                    "authorization.",
                    move.pay_now_journal_id.display_name,
                )
            )
        return result
