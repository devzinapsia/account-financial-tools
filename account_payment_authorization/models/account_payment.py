from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

ACTIVITY_TYPE_XMLID = "mail.mail_activity_data_todo"


class AccountPayment(models.Model):
    _inherit = "account.payment"

    authorization_state = fields.Selection(
        selection=[
            ("not_required", "Not required"),
            ("to_authorize", "To authorize"),
            ("authorized", "Authorized"),
            ("rejected", "Rejected"),
        ],
        string="Authorization status",
        default="not_required",
        required=True,
        tracking=True,
        copy=False,
    )
    matched_scheme_ids = fields.Many2many(
        "account.payment.authorization.scheme",
        string="Matched authorization schemes",
        compute="_compute_matched_scheme_ids",
        store=True,
    )
    pending_authorizer_ids = fields.Many2many(
        "res.users",
        string="Pending authorizers",
        compute="_compute_pending_authorizer_ids",
        store=True,
    )
    authorized_by_id = fields.Many2one(
        "res.users",
        string="Authorized by",
        tracking=True,
        copy=False,
    )
    authorization_reject_reason = fields.Text(
        string="Rejection reason",
        copy=False,
    )

    @api.depends(
        "payment_type",
        "partner_type",
        "company_id",
        "partner_id",
        "payment_method_line_id",
        "amount",
        "date",
        "journal_id",
        "currency_id",
        "invoice_ids",
        "invoice_ids.classification_id",
        "invoice_ids.partner_id",
        "invoice_ids.invoice_date",
    )
    def _compute_matched_scheme_ids(self):
        # Schemes match through an arbitrary, admin-configured domain (see
        # account.payment.authorization.scheme.domain), so the exact set of
        # fields it can reference isn't known here -- the @api.depends above
        # is a best-effort list of the fields most likely to be used in a
        # condition, not an exhaustive one. This only affects how fresh the
        # *stored/displayed* value is on an untouched draft payment: every
        # authorization-sensitive decision (action_post / authorize /
        # reject) calls _refresh_authorization_state() first, which forces a
        # fully fresh evaluation regardless of whether this compute would
        # have been triggered automatically.
        scheme_model = self.env["account.payment.authorization.scheme"]
        for payment in self:
            if payment.payment_type != "outbound" or payment.partner_type != "supplier":
                payment.matched_scheme_ids = False
                continue
            candidates = scheme_model.search(
                [
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", payment.company_id.id),
                ]
            )
            payment.matched_scheme_ids = candidates.filtered(
                lambda scheme, payment=payment: scheme._matches_payment(payment)
            )

    @api.depends("matched_scheme_ids.authorized_user_ids", "matched_scheme_ids.block_payment")
    def _compute_pending_authorizer_ids(self):
        for payment in self:
            # A scheme with "Always block" checked never contributes
            # approvers, regardless of what's in its authorized_user_ids --
            # that field is meant to be ignored in that case (see the field's
            # help text).
            open_schemes = payment.matched_scheme_ids.filtered(lambda s: not s.block_payment)
            payment.pending_authorizer_ids = open_schemes.authorized_user_ids

    def _refresh_authorization_state(self):
        """Force a fresh recompute of the matching fields against the
        current scheme configuration and invoice state, instead of trusting
        a possibly stale stored value. Editing a scheme's conditions (e.g.
        adding a partner) does not, by itself, invalidate the stored compute
        on existing draft payments, since there is no stored relation to
        depend on before the match is evaluated. Calling this before every
        authorization-sensitive decision (post / authorize / reject) keeps
        those decisions always based on the live configuration.
        """
        self.invalidate_recordset(["matched_scheme_ids", "pending_authorizer_ids"])

    def _create_authorization_activities(self):
        for payment in self:
            for user in payment.pending_authorizer_ids:
                payment.activity_schedule(
                    ACTIVITY_TYPE_XMLID,
                    summary=_("Payment authorization requested"),
                    note=_(
                        "%(requester)s requested your authorization to confirm "
                        "payment %(payment)s (%(amount)s %(currency)s) to "
                        "%(partner)s.",
                        requester=self.env.user.display_name,
                        payment=payment.display_name,
                        amount=payment.amount,
                        currency=payment.currency_id.name,
                        partner=payment.partner_id.display_name,
                    ),
                    user_id=user.id,
                )
            if payment.pending_authorizer_ids:
                payment.message_post(
                    body=_(
                        "Authorization requested from: %s",
                        ", ".join(payment.pending_authorizer_ids.mapped("display_name")),
                    )
                )
                continue

            blocking_schemes = payment.matched_scheme_ids.filtered("block_payment")
            if blocking_schemes:
                payment.message_post(
                    body=_(
                        "This payment is permanently blocked by the following "
                        "scheme(s): %s.",
                        ", ".join(blocking_schemes.mapped("name")),
                    )
                )
            else:
                payment.message_post(
                    body=_(
                        "This payment matches an authorization scheme with no "
                        "authorized users configured. It cannot be approved "
                        "until a user is added to that scheme."
                    )
                )

    def action_post(self):
        self._refresh_authorization_state()

        to_confirm = self.browse()
        blocked_payments = self.browse()
        for payment in self:
            if payment.move_id and payment.move_id.state != "draft":
                # The journal entry is already posted: this is an
                # idempotent re-confirmation attempt (or a payment that was
                # already fully confirmed), not a first-time authorization
                # decision point. Note that `payment.state` is *not* a
                # reliable "already confirmed" signal here: the Register
                # Payment wizard's create() flow (via
                # `_generate_journal_entry()`, triggered because it always
                # passes `write_off_line_vals`) sets `state` to
                # 'in_process' *before* `action_post()` is even called,
                # while the journal entry itself is still left in 'draft'
                # until `action_post()` actually runs.
                to_confirm += payment
                continue

            if payment.payment_type != "outbound" or payment.partner_type != "supplier":
                payment.authorization_state = "not_required"
                to_confirm += payment
                continue

            if not payment.matched_scheme_ids:
                payment.authorization_state = "not_required"
                to_confirm += payment
            elif self.env.user in payment.pending_authorizer_ids:
                payment.authorization_state = "authorized"
                payment.authorized_by_id = self.env.user
                to_confirm += payment
            else:
                payment.authorization_state = "to_authorize"
                # See the note above: the wizard may have already flipped
                # `state` to 'in_process' before this method ever ran, even
                # though the payment was never actually confirmed (the
                # journal entry is still draft). Revert it to 'draft' so
                # the payment accurately reflects that it is pending, and
                # so the later action_post() call from
                # action_authorize_payment() posts the journal entry
                # normally. The journal entry itself does not need
                # resetting: it is already 'draft' (that's what the branch
                # above checked), and account.move.button_draft() refuses
                # to run on a move that isn't 'posted'/'cancel'.
                payment.state = "draft"
                payment._create_authorization_activities()
                blocked_payments += payment

        if to_confirm:
            super(AccountPayment, to_confirm).action_post()

        if blocked_payments and not to_confirm:
            if len(blocked_payments) == 1:
                raise UserError(
                    _(
                        "This payment requires authorization before it can be "
                        "confirmed. An activity has been assigned to the "
                        "authorized user(s)."
                    )
                )
            raise UserError(
                _(
                    "These payments require authorization before they can be "
                    "confirmed: %s. An activity has been assigned to the "
                    "authorized user(s) of each.",
                    ", ".join(blocked_payments.mapped("display_name")),
                )
            )
        return True

    def action_authorize_payment(self):
        self._refresh_authorization_state()
        for payment in self:
            if payment.authorization_state != "to_authorize":
                raise UserError(_("This payment is not pending authorization."))
            if self.env.user not in payment.pending_authorizer_ids:
                raise AccessError(_("You are not allowed to authorize this payment."))

        for payment in self:
            payment.authorization_state = "authorized"
            payment.authorized_by_id = self.env.user
            payment.activity_ids.filtered(
                lambda activity: activity.activity_type_id
                == self.env.ref(ACTIVITY_TYPE_XMLID)
            ).action_feedback(
                feedback=_("Payment authorized by %s.", self.env.user.display_name)
            )
            payment.message_post(
                body=_("Payment authorized by %s.", self.env.user.display_name)
            )

        super(AccountPayment, self).action_post()
        return True

    def action_reject_payment(self):
        self.ensure_one()
        self._refresh_authorization_state()
        if self.authorization_state != "to_authorize":
            raise UserError(_("This payment is not pending authorization."))
        if self.env.user not in self.pending_authorizer_ids:
            raise AccessError(_("You are not allowed to reject this payment."))
        return {
            "name": _("Reject payment"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment.authorization.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_payment_id": self.id},
        }
