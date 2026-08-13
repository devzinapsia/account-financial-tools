from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

ACTIVITY_TYPE_XMLID = "mail.mail_activity_data_todo"


class AccountPaymentAuthorizationRejectWizard(models.TransientModel):
    _name = "account.payment.authorization.reject.wizard"
    _description = "Reject Payment Authorization"

    payment_id = fields.Many2one(
        "account.payment",
        required=True,
        readonly=True,
    )
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        payment = self.payment_id
        payment._refresh_authorization_state()
        if payment.authorization_state != "to_authorize":
            raise UserError(_("This payment is not pending authorization."))
        if self.env.user not in payment.pending_authorizer_ids:
            raise AccessError(_("You are not allowed to reject this payment."))

        payment.authorization_state = "rejected"
        payment.authorization_reject_reason = self.reason
        payment.activity_ids.filtered(
            lambda activity: activity.activity_type_id
            == self.env.ref(ACTIVITY_TYPE_XMLID)
        ).action_feedback(
            feedback=_(
                "Payment rejected by %(user)s.\nReason: %(reason)s",
                user=self.env.user.display_name,
                reason=self.reason,
            )
        )
        payment.message_post(
            body=_(
                "Payment rejected by %(user)s.<br/>Reason: %(reason)s",
                user=self.env.user.display_name,
                reason=self.reason,
            )
        )
        if payment.create_uid:
            payment.activity_schedule(
                ACTIVITY_TYPE_XMLID,
                summary=_("Payment authorization rejected"),
                note=_(
                    "%(approver)s rejected the authorization request for "
                    "payment %(payment)s.<br/>Reason: %(reason)s",
                    approver=self.env.user.display_name,
                    payment=payment.display_name,
                    reason=self.reason,
                ),
                user_id=payment.create_uid.id,
            )
        return {"type": "ir.actions.act_window_close"}
