from odoo import _, api, models
from odoo.tools.safe_eval import safe_eval

CONFIRMED_STATES = ("in_process", "paid")


class AccountPayment(models.Model):
    _name = "account.payment"
    _inherit = ["account.payment", "account.review.mixin"]

    # ------------------------------------------------------------------
    # account.review.mixin hooks
    # ------------------------------------------------------------------

    @api.depends("state", "payment_type", "partner_type")
    def _compute_review_is_reviewable(self):
        return super()._compute_review_is_reviewable()

    def _review_reviewable_domain(self):
        return [
            ("state", "in", CONFIRMED_STATES),
            ("payment_type", "=", "outbound"),
            ("partner_type", "=", "supplier"),
        ]

    def _review_reviewer_group(self):
        return "account_payment_review.group_payment_reviewer"

    def _review_answer_group(self):
        return "account.group_account_invoice"

    def _review_subtype_xmlid(self):
        return "account_payment_review.mt_payment_review"

    def _review_observation_activity_xmlid(self):
        return "account_payment_review.mail_activity_payment_review_observation"

    def _review_answer_activity_xmlid(self):
        return "account_payment_review.mail_activity_payment_review_answer"

    def _review_answer_days(self):
        return self.company_id.payment_review_answer_days

    def _review_observation_hint(self):
        return _(
            "To answer, mark this activity as done and write your answer, "
            "or use the 'Answer observations' button of the payment."
        )

    def _review_answer_hint(self):
        return _(
            "Marking this activity as done signs the payment off as "
            "reviewed. To record new observations instead, use the 'Mark "
            "as reviewed' button of the payment."
        )

    def _review_amount(self):
        """Amount compared against the company's "Review from amount"
        setting, in company currency. Extended by glue modules whose
        payments carry their real amount somewhere else."""
        self.ensure_one()
        return abs(self.amount_company_currency_signed)

    def _review_initial_state(self):
        self.ensure_one()
        company = self.company_id
        if not company.payment_review_enabled:
            return False
        min_amount = company.payment_review_min_amount
        if min_amount and company.currency_id.compare_amounts(self._review_amount(), min_amount) < 0:
            return "not_required"
        domain = safe_eval(company.payment_review_domain or "[]", {"uid": self.env.uid})
        if domain and not self.filtered_domain(domain):
            return "not_required"
        return "pending"

    # ------------------------------------------------------------------
    # ORM: stamp the issuer and the initial review status on confirmation
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments.filtered(lambda p: p.state in CONFIRMED_STATES)._review_on_confirm()
        return payments

    def write(self, vals):
        # Confirmation is detected on the state transition rather than in
        # action_post(): the "Register Payment" wizard writes 'in_process'
        # on its own before calling action_post(), and action_post() itself
        # only assigns the state.
        to_confirm = to_reset = self.browse()
        if vals.get("state") in CONFIRMED_STATES:
            to_confirm = self.filtered(lambda p: p.state not in CONFIRMED_STATES)
        elif vals.get("state") == "draft":
            to_reset = self.filtered(lambda p: p.state != "draft")
        result = super().write(vals)
        to_reset._review_reset()
        to_confirm._review_on_confirm()
        return result

    def _review_on_confirm(self):
        if not self:
            return
        user = self.env.user
        # Payments confirmed by a cron/automated process: their creator is
        # the most meaningful issuer we have.
        trusted_user = not user._is_superuser() and not user.share
        for payment in self:
            issuer = user if trusted_user else payment.create_uid
            if issuer != payment.review_issuer_id:
                payment.sudo().write({"review_issuer_id": issuer.id})
        self._review_classify_on_confirm()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_review_wizard(self):
        self._review_check_can_review()
        return {
            "type": "ir.actions.act_window",
            "name": _("Review payments"),
            "res_model": "account.payment.review.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_model": self._name, "active_ids": self.ids},
        }

    def action_open_review_answer_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Answer observations"),
            "res_model": "account.payment.review.answer.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_model": self._name, "active_id": self.id},
        }
