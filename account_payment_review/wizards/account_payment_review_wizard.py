from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

RESULT_SELECTION = [
    ("reviewed", "OK"),
    ("observed", "With observations"),
    ("not_required", "Not required"),
]


class AccountPaymentReviewWizard(models.TransientModel):
    """Review one or several vendor payments at once. With a single
    payment the form shows just a result and a comment; with several, one
    editable line per payment, each with its own result and comment."""

    _name = "account.payment.review.wizard"
    _description = "Review payments"

    line_ids = fields.One2many(
        "account.payment.review.wizard.line",
        "wizard_id",
        string="Payments",
    )
    is_single = fields.Boolean(compute="_compute_is_single")
    result = fields.Selection(
        selection=RESULT_SELECTION,
        string="Result",
        default="reviewed",
        required=True,
    )
    comment = fields.Text(string="Comment")

    @api.depends("line_ids")
    def _compute_is_single(self):
        for wizard in self:
            wizard.is_single = len(wizard.line_ids) == 1

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        context = self.env.context
        if "line_ids" in fields_list and context.get("active_model") == "account.payment":
            payments = self.env["account.payment"].browse(context.get("active_ids") or [])
            if not payments:
                raise UserError(_("Select at least one payment to review."))
            payments._review_check_can_review()
            res["line_ids"] = [Command.create({"payment_id": payment.id}) for payment in payments]
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("There are no payments left to review."))
        if self.is_single:
            self.line_ids.write({"result": self.result, "comment": self.comment})
        missing = self.line_ids.filtered(lambda line: line.result == "observed" and not (line.comment or "").strip())
        if missing:
            raise UserError(
                _(
                    "Write a comment for every payment with observations: %s",
                    ", ".join(missing.payment_id.mapped("display_name")),
                )
            )
        for line in self.line_ids:
            line.payment_id._review_set_result(line.result, line.comment)
        return {"type": "ir.actions.act_window_close"}


class AccountPaymentReviewWizardLine(models.TransientModel):
    _name = "account.payment.review.wizard.line"
    _description = "Review payments line"

    wizard_id = fields.Many2one(
        "account.payment.review.wizard",
        required=True,
        ondelete="cascade",
    )
    payment_id = fields.Many2one(
        "account.payment",
        string="Payment",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(related="payment_id.partner_id")
    date = fields.Date(related="payment_id.date")
    journal_id = fields.Many2one(related="payment_id.journal_id")
    payment_method_line_id = fields.Many2one(related="payment_id.payment_method_line_id")
    amount = fields.Monetary(related="payment_id.amount", currency_field="currency_id")
    currency_id = fields.Many2one(related="payment_id.currency_id")
    review_state = fields.Selection(related="payment_id.review_state", string="Current review status")
    result = fields.Selection(
        selection=RESULT_SELECTION,
        string="Result",
        default="reviewed",
        required=True,
    )
    comment = fields.Text(string="Comment")
