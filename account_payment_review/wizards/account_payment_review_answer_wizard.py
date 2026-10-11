from odoo import api, fields, models


class AccountPaymentReviewAnswerWizard(models.TransientModel):
    _name = "account.payment.review.answer.wizard"
    _description = "Answer payment review observations"

    payment_id = fields.Many2one(
        "account.payment",
        string="Payment",
        required=True,
        ondelete="cascade",
    )
    review_user_id = fields.Many2one(related="payment_id.review_user_id")
    review_comment = fields.Text(related="payment_id.review_comment", string="Observations")
    answer = fields.Text(string="Answer", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        context = self.env.context
        if "payment_id" in fields_list and context.get("active_model") == "account.payment" and context.get("active_id"):
            res["payment_id"] = context["active_id"]
        return res

    def action_confirm(self):
        self.ensure_one()
        self.payment_id._review_answer(self.answer)
        return {"type": "ir.actions.act_window_close"}
