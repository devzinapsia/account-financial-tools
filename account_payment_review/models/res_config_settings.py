from odoo import Command, api, fields, models

REVIEWER_GROUP_XMLID = "account_payment_review.group_payment_reviewer"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    payment_review_enabled = fields.Boolean(
        related="company_id.payment_review_enabled",
        readonly=False,
    )
    payment_review_min_amount = fields.Monetary(
        related="company_id.payment_review_min_amount",
        readonly=False,
    )
    payment_review_domain = fields.Char(
        related="company_id.payment_review_domain",
        readonly=False,
    )
    payment_review_answer_days = fields.Integer(
        related="company_id.payment_review_answer_days",
        readonly=False,
    )
    # A shortcut to the "Payment reviewer" group's members, so the reviewers
    # can be picked from the review settings instead of from each user's
    # form. The group stays the single source of truth (menus, buttons and
    # read access depend on it), so this applies to every company.
    payment_reviewer_ids = fields.Many2many(
        "res.users",
        string="Payment reviewers",
        compute="_compute_payment_reviewer_ids",
        inverse="_inverse_payment_reviewer_ids",
        readonly=False,
        domain=[("share", "=", False)],
        help="Users allowed to review vendor payments, in every company. "
        "Same as giving them the 'Payment reviewer' access right on their "
        "user form.",
    )

    @api.depends("company_id")
    def _compute_payment_reviewer_ids(self):
        reviewers = self.env.ref(REVIEWER_GROUP_XMLID).sudo().user_ids
        for settings in self:
            settings.payment_reviewer_ids = reviewers

    def _inverse_payment_reviewer_ids(self):
        group = self.env.ref(REVIEWER_GROUP_XMLID).sudo()
        for settings in self:
            if group.user_ids != settings.payment_reviewer_ids:
                group.write({"user_ids": [Command.set(settings.payment_reviewer_ids.ids)]})
