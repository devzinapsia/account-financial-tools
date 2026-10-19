from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

ACTIVITY_TYPE_XMLID = "mail.mail_activity_data_todo"
VENDOR_BILL_TYPES = ("in_invoice", "in_refund")
# Set while the moves are actually being posted (see _post()), so that the
# writes core makes on them during posting (name, date, lines...) are not
# mistaken for a user edit that invalidates an authorization.
POSTING_CONTEXT_KEY = "vendor_bill_authorization_posting"


class AccountMove(models.Model):
    _inherit = "account.move"

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
    matched_policy_ids = fields.Many2many(
        "account.vendor.bill.authorization.policy",
        relation="account_move_vendor_bill_authorization_policy_rel",
        string="Matched authorization policies",
        compute="_compute_matched_policy_ids",
        store=True,
        copy=False,
    )
    pending_authorizer_ids = fields.Many2many(
        "res.users",
        relation="account_move_vendor_bill_pending_authorizer_rel",
        string="Pending authorizers",
        compute="_compute_pending_authorizer_ids",
        store=True,
        copy=False,
    )
    is_blocked = fields.Boolean(
        string="Blocked by policy",
        compute="_compute_is_blocked",
        store=True,
        copy=False,
        help="True if at least one matching authorization policy has "
        "'Always block' checked: this vendor bill can then never be "
        "confirmed, by anyone.",
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
    )
    def _compute_matched_policy_ids(self):
        # Policies match through an arbitrary, admin-configured domain (see
        # account.vendor.bill.authorization.policy.domain), so the exact set
        # of fields it can reference isn't known here -- the @api.depends
        # above is a best-effort list of the fields most likely to be used
        # in a condition, not an exhaustive one. This only affects how fresh
        # the *stored/displayed* value is on an untouched draft bill: every
        # authorization-sensitive decision (post / authorize / reject /
        # unauthorize) calls _refresh_authorization_state() first, which
        # forces a fully fresh evaluation regardless of whether this compute
        # would have been triggered automatically.
        #
        # Policies are searched as superuser: whether a bill needs
        # authorization must not depend on whether the user confirming it
        # can read the policy configuration.
        policy_model = self.env["account.vendor.bill.authorization.policy"].sudo()
        candidates_by_company = {}
        for move in self:
            if move.move_type not in VENDOR_BILL_TYPES:
                move.matched_policy_ids = False
                continue
            company_id = move.company_id.id
            if company_id not in candidates_by_company:
                candidates_by_company[company_id] = policy_model.search(
                    [
                        "|",
                        ("company_id", "=", False),
                        ("company_id", "=", company_id),
                    ]
                )
            move.matched_policy_ids = candidates_by_company[company_id].filtered(
                lambda policy, move=move: policy._matches_bill(move)
            )

    @api.depends("matched_policy_ids.authorized_user_ids", "matched_policy_ids.always_block")
    def _compute_pending_authorizer_ids(self):
        for move in self:
            # A policy with "Always block" checked never contributes
            # approvers, regardless of what's in its authorized_user_ids --
            # that field is meant to be ignored in that case (see the
            # field's help text).
            open_policies = move.matched_policy_ids.filtered(lambda p: not p.always_block)
            move.pending_authorizer_ids = open_policies.authorized_user_ids

    @api.depends("matched_policy_ids.always_block")
    def _compute_is_blocked(self):
        for move in self:
            move.is_blocked = any(move.matched_policy_ids.mapped("always_block"))

    def _get_authorization_sensitive_fields(self):
        """Fields an authorization policy's domain could plausibly key off
        of; see write() below. Kept in sync by hand with
        _compute_matched_policy_ids's own @api.depends, since a policy's
        domain is admin-configured and arbitrary -- there's no way to know
        exactly which fields it references, only a best-effort list of the
        ones most likely to. Line edits are covered through
        invoice_line_ids/line_ids, since that's how the form (and any
        one2many edit) writes them. Extend via super() if needed.
        """
        return {
            "move_type",
            "company_id",
            "partner_id",
            "journal_id",
            "currency_id",
            "invoice_date",
            "date",
            "classification_id",
            "invoice_line_ids",
            "line_ids",
            "fiscal_position_id",
            "invoice_payment_term_id",
        }

    def _is_awaiting_authorization(self):
        """True if this vendor bill can't be paid (nor reconciled) yet: it
        was confirmed while matching a policy and is still awaiting
        authorization, or it was rejected.
        """
        self.ensure_one()
        return self.move_type in VENDOR_BILL_TYPES and self.authorization_state in (
            "to_authorize",
            "rejected",
        )

    def write(self, vals):
        if self.env.context.get(POSTING_CONTEXT_KEY):
            return super().write(vals)

        # If a vendor bill was already authorized (or rejected) and this
        # write touches a field an authorization policy's domain could
        # plausibly key off of (most obviously the lines/amount, but also
        # the vendor, journal, currency, dates or classification), that
        # earlier decision no longer says anything about the bill as it
        # exists now -- someone could otherwise get a small amount
        # authorized, then change it before paying without ever being
        # re-checked. Capture who needs to be reset *before* the write
        # changes anything.
        to_reset_on_edit = self.browse()
        if self._get_authorization_sensitive_fields().intersection(vals):
            to_reset_on_edit = self.filtered(
                lambda m: m.move_type in VENDOR_BILL_TYPES
                and m.state in ("draft", "posted")
                and m.authorization_state in ("authorized", "rejected")
            )
        # A confirmed bill going back to draft loses whatever authorization
        # state it had: it is evaluated again, from scratch, when it is
        # confirmed again.
        to_reset_on_draft = self.browse()
        if vals.get("state") == "draft":
            to_reset_on_draft = self.filtered(
                lambda m: m.move_type in VENDOR_BILL_TYPES and m.state != "draft"
            )
        to_reset_on_edit -= to_reset_on_draft
        previous = {
            move.id: (move.authorization_state, move.authorized_by_id)
            for move in to_reset_on_edit | to_reset_on_draft
        }

        result = super().write(vals)

        for move in to_reset_on_draft:
            previous_state, previous_authorizer = previous[move.id]
            move._clear_authorization_requests()
            if previous_state != "not_required":
                super(AccountMove, move).write(
                    {"authorization_state": "not_required", "authorized_by_id": False}
                )
            if previous_state == "authorized":
                move.message_post(
                    body=_(
                        "Authorization reset: this vendor bill was reset to "
                        "draft after %s authorized it, so it will need to be "
                        "authorized again once it is confirmed.",
                        previous_authorizer.display_name or _("an authorizer"),
                    )
                )

        for move in to_reset_on_edit:
            previous_state, previous_authorizer = previous[move.id]
            if previous_state == "rejected":
                body = _(
                    "Rejection reset: this vendor bill's data changed after it "
                    "was rejected, so it is pending authorization again."
                )
            else:
                body = _(
                    "Authorization reset: this vendor bill's data changed "
                    "after %s authorized it, so it must be authorized again "
                    "before it can be paid.",
                    previous_authorizer.display_name or _("an authorizer"),
                )
            if move.state == "posted":
                # Confirmed: pending again, and the authorizers are asked
                # again.
                super(AccountMove, move).write(
                    {"authorization_state": "to_authorize", "authorized_by_id": False}
                )
                move.message_post(body=body)
                move._refresh_authorization_state()
                move._apply_authorization_requirement()
            else:
                # Draft (left over from versions that authorized before
                # confirming): evaluated again when it is confirmed.
                super(AccountMove, move).write(
                    {"authorization_state": "not_required", "authorized_by_id": False}
                )
                move.message_post(body=body)

        if vals.get("state") and vals["state"] not in ("draft", "posted"):
            # E.g. cancelled: nobody needs to act on its requests anymore.
            # Posting is handled in _post().
            self._clear_authorization_requests()
        return result

    def _refresh_authorization_state(self):
        """Force a real recompute of the matching fields against the current
        policy configuration, instead of trusting a possibly stale stored
        value. Editing a policy's conditions (e.g. adding a vendor) does
        not, by itself, invalidate the stored compute on existing bills,
        since there is no stored relation to depend on before the match is
        evaluated. Calling this before every authorization-sensitive
        decision keeps those decisions always based on the live
        configuration. It never changes authorization_state by itself:
        whether a bill requires authorization is decided when it is
        confirmed (see _post()).
        """
        moves = self.exists()
        if not moves:
            return
        fnames = ["matched_policy_ids", "pending_authorizer_ids", "is_blocked"]
        for fname in fnames:
            self.env.add_to_compute(self._fields[fname], moves)
        moves._recompute_recordset(fnames)

    def _get_blocked_error_message(self):
        blocking_policies = self.matched_policy_ids.filtered("always_block")
        return _(
            "This vendor bill could not be confirmed because it does not "
            "comply with the authorization policies. Check whether the "
            "vendor bill has any of the following:\n\n"
            "- Missing required information.\n"
            "- A field value that is inconsistent with internal rules.\n\n"
            "Please validate the information or check with your "
            "supervisor.\n\n"
            "Blocking policy/policies: %s",
            ", ".join(blocking_policies.mapped("name")),
        )

    @api.model
    def _get_authorization_request_summaries(self):
        """The summary of the activities _request_authorization() schedules,
        in every installed language: the summary is stored already
        translated into the requester's language, and it is what tells these
        activities apart from any other To-Do on the bill.
        """
        # The untranslated source is always included: it is what gets stored
        # for any requester whose language has no translation, and en_US is
        # not necessarily among the installed languages.
        source = "Vendor bill authorization requested"
        return {source} | {
            self.with_context(lang=code).env._("Vendor bill authorization requested")
            for code, _name in self.env["res.lang"].get_installed()
        }

    def _get_authorization_requests(self):
        """Open "authorization requested" activities of these bills -- not
        any other To-Do, nor the rejected/revoked notices sent to whoever
        loaded the bill. Read as superuser: the user acting on the bill may
        not see the other authorizers' activities.
        """
        if not self:
            return self.env["mail.activity"]
        todo = self.env.ref(ACTIVITY_TYPE_XMLID)
        return (
            self.env["mail.activity"]
            .sudo()
            .search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "in", self.ids),
                    ("activity_type_id", "=", todo.id),
                    ("summary", "in", list(self._get_authorization_request_summaries())),
                ]
            )
        )

    def _clear_authorization_requests(self):
        """Remove the pending "authorization requested" activities once
        nobody needs to act on them anymore (authorized, rejected, no
        longer required, reset to draft, cancelled). They are deleted rather
        than marked as done on purpose: marking an activity as done posts
        one chatter message per activity (one per authorizer), while the
        decision itself is already logged by this module's own message.
        """
        self._get_authorization_requests().unlink()

    @api.model
    def _cleanup_stale_authorization_requests(self):
        """Remove "authorization requested" activities that nobody needs to
        act on: those on bills not pending authorization (confirmed and
        "To authorize"), plus duplicates on bills still pending. Used by
        the migrations. Returns the number of activities removed.
        """
        todo = self.env.ref(ACTIVITY_TYPE_XMLID)
        activities = (
            self.env["mail.activity"]
            .sudo()
            .search(
                [
                    ("res_model", "=", self._name),
                    ("activity_type_id", "=", todo.id),
                    ("summary", "in", list(self._get_authorization_request_summaries())),
                ],
                order="id",
            )
        )
        moves = self.sudo().browse(set(activities.mapped("res_id"))).exists()
        pending = moves.filtered(
            lambda m: m.move_type in VENDOR_BILL_TYPES
            and m.state == "posted"
            and m.authorization_state == "to_authorize"
        )
        to_remove = self.env["mail.activity"].sudo()
        seen = set()
        for activity in activities:
            key = (activity.res_id, activity.user_id.id)
            if activity.res_id not in pending.ids or key in seen:
                to_remove |= activity
            seen.add(key)
        to_remove.unlink()
        return len(to_remove)

    def _request_authorization(self):
        """Ask every pending authorizer of these confirmed bills for their
        authorization, through an activity. Authorizers who already have an
        open request are not asked again (and the chatter only logs when
        someone new was asked).
        """
        for move in self:
            already_asked = move._get_authorization_requests().user_id
            new_authorizers = move.pending_authorizer_ids - already_asked
            for user in new_authorizers:
                move.activity_schedule(
                    ACTIVITY_TYPE_XMLID,
                    summary=_("Vendor bill authorization requested"),
                    note=_(
                        "%(requester)s confirmed vendor bill %(bill)s "
                        "(%(amount)s %(currency)s) from %(partner)s: it "
                        "requires your authorization before it can be paid.",
                        requester=self.env.user.display_name,
                        bill=move.display_name,
                        amount=move.amount_total,
                        currency=move.currency_id.name,
                        partner=move.partner_id.display_name,
                    ),
                    user_id=user.id,
                )
            if new_authorizers:
                move.message_post(
                    body=_(
                        "Authorization requested from: %s",
                        ", ".join(new_authorizers.mapped("display_name")),
                    )
                )
            elif not move.pending_authorizer_ids:
                move.message_post(
                    body=_(
                        "This vendor bill matches an authorization policy with "
                        "no authorized users configured. It cannot be "
                        "authorized (nor paid) until a user is added to that "
                        "policy."
                    )
                )

    def _apply_authorization_requirement(self):
        """Decide, for confirmed vendor bills, whether they require
        authorization before they can be paid, from the policies they match
        (already refreshed by the caller). An authorization already given
        (left over from versions that authorized before confirming) stands.
        """
        for move in self:
            if move.move_type not in VENDOR_BILL_TYPES or move.state != "posted":
                continue
            if not move.matched_policy_ids:
                if move.authorization_state != "not_required":
                    super(AccountMove, move).write(
                        {"authorization_state": "not_required", "authorized_by_id": False}
                    )
                move._clear_authorization_requests()
                continue
            if move.authorization_state == "authorized":
                move.message_post(
                    body=_(
                        "Vendor bill confirmed by %(user)s (authorized earlier "
                        "by %(authorized_by)s).",
                        user=self.env.user.display_name,
                        authorized_by=move.authorized_by_id.display_name,
                    )
                )
                continue
            if move.authorization_state != "to_authorize":
                super(AccountMove, move).write(
                    {"authorization_state": "to_authorize", "authorized_by_id": False}
                )
            move._request_authorization()

    def _check_vendor_bill_authorization_before_post(self):
        """Run before confirming, whatever the path (the Confirm button, the
        "Post entries" list action, the auto-post cron, third-party
        background posting...): a vendor bill matching a policy with
        "Always block" can never be confirmed. Any other matching policy
        does not prevent confirming: it is evaluated once the bill is
        confirmed, and then prevents paying it until it is authorized.
        """
        moves = self.filtered(lambda m: m.move_type in VENDOR_BILL_TYPES and m.state == "draft")
        if not moves:
            return
        moves._refresh_authorization_state()
        blocked = moves.filtered("is_blocked")
        if blocked:
            raise UserError(blocked._get_blocked_error_message())

    def _post(self, soft=True):
        if self.env.context.get("move_reverse_cancel"):
            # Full refund / "modify" reversal of an already posted vendor
            # bill: core creates and posts the credit note in one go to
            # cancel the original; it is not a new document to be approved.
            return super(AccountMove, self.with_context(**{POSTING_CONTEXT_KEY: True}))._post(soft=soft)
        self._check_vendor_bill_authorization_before_post()
        to_evaluate = self.filtered(lambda m: m.move_type in VENDOR_BILL_TYPES and m.state == "draft")
        posted = super(AccountMove, self.with_context(**{POSTING_CONTEXT_KEY: True}))._post(soft=soft)
        to_evaluate.filtered(lambda m: m.state == "posted")._apply_authorization_requirement()
        return posted

    # -- Payment ---------------------------------------------------------

    def _get_payment_blocked_error_message(self):
        return _(
            "The following vendor bills can't be paid until they are "
            "authorized (they are pending authorization or were rejected): "
            "%s.",
            ", ".join(self.mapped("display_name")),
        )

    def _check_vendor_bill_authorization_before_payment(self):
        """Refuse to pay (or reconcile) vendor bills awaiting authorization
        or rejected.
        """
        awaiting = self.filtered(lambda m: m._is_awaiting_authorization())
        if awaiting:
            raise UserError(awaiting._get_payment_blocked_error_message())

    def action_register_payment(self):
        self._check_vendor_bill_authorization_before_payment()
        return super().action_register_payment()

    def action_force_register_payment(self):
        self._check_vendor_bill_authorization_before_payment()
        return super().action_force_register_payment()

    # -- Authorization actions -------------------------------------------

    def _check_bill_pending_authorization(self, access_error_message):
        self._refresh_authorization_state()
        for move in self:
            if (
                move.move_type not in VENDOR_BILL_TYPES
                or move.state != "posted"
                or move.authorization_state != "to_authorize"
            ):
                raise UserError(_("This vendor bill is not pending authorization."))
            if self.env.user not in move.pending_authorizer_ids:
                raise AccessError(access_error_message)

    def action_authorize_bill(self):
        """Authorize a confirmed vendor bill, so that it can be paid. Paying
        is a deliberately separate step: once authorized, anyone with the
        regular permission to pay bills can pay it.
        """
        self._check_bill_pending_authorization(_("You are not allowed to authorize this vendor bill."))
        for move in self:
            move.write({"authorization_state": "authorized", "authorized_by_id": self.env.user.id})
            move._clear_authorization_requests()
            move.message_post(
                body=_(
                    "Vendor bill authorized by %s. It can now be paid.",
                    self.env.user.display_name,
                )
            )
        return True

    def action_unauthorize_bill(self):
        """Revert an authorized vendor bill that has no payment yet back to
        "to_authorize", undoing a mistaken Authorize click. Any user who is
        currently a pending authorizer of the bill can do it, not only the
        one who authorized it. The bill can be authorized again afterwards,
        by the same or a different authorizer, with no restriction.
        """
        self._refresh_authorization_state()
        for move in self:
            if (
                move.move_type not in VENDOR_BILL_TYPES
                or move.state != "posted"
                or move.authorization_state != "authorized"
            ):
                raise UserError(_("This vendor bill is not currently authorized."))
            if move.payment_state != "not_paid":
                raise UserError(
                    _(
                        "The authorization of vendor bill %s can't be revoked: "
                        "it already has payments.",
                        move.display_name,
                    )
                )
            if self.env.user not in move.pending_authorizer_ids:
                raise AccessError(_("You are not allowed to unauthorize this vendor bill."))

        for move in self:
            previous_authorizer = move.authorized_by_id
            move.write({"authorization_state": "to_authorize", "authorized_by_id": False})
            move.message_post(
                body=_(
                    "Authorization revoked by %s. Awaiting authorization again.",
                    self.env.user.display_name,
                )
            )
            if move.create_uid:
                move.activity_schedule(
                    ACTIVITY_TYPE_XMLID,
                    summary=_("Vendor bill authorization revoked"),
                    note=_(
                        "%(revoker)s revoked the authorization for vendor bill "
                        "%(bill)s, previously authorized by %(previous)s.",
                        revoker=self.env.user.display_name,
                        bill=move.display_name,
                        previous=previous_authorizer.display_name or _("an authorizer"),
                    ),
                    user_id=move.create_uid.id,
                )
        return True

    def action_reject_bill(self):
        self.ensure_one()
        self._check_bill_pending_authorization(_("You are not allowed to reject this vendor bill."))
        return {
            "name": _("Reject vendor bill"),
            "type": "ir.actions.act_window",
            "res_model": "account.vendor.bill.authorization.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _reject_bill(self, reason):
        """Record the rejection; called by the reject wizard once the
        reason has been entered. Permission is re-checked here, server-side.
        A rejected bill can't be paid: to fix it, reset it to draft, edit it
        and confirm it again (authorization is then requested again), or
        cancel it with a credit note.
        """
        self.ensure_one()
        self._check_bill_pending_authorization(_("You are not allowed to reject this vendor bill."))
        self.write({"authorization_state": "rejected", "authorization_reject_reason": reason})
        self._clear_authorization_requests()
        self.message_post(
            body=Markup(_("Vendor bill rejected by %(user)s.<br/>Reason: %(reason)s"))
            % {"user": self.env.user.display_name, "reason": reason}
        )
        if self.create_uid:
            self.activity_schedule(
                ACTIVITY_TYPE_XMLID,
                summary=_("Vendor bill authorization rejected"),
                note=Markup(
                    _(
                        "%(approver)s rejected the authorization request for "
                        "vendor bill %(bill)s.<br/>Reason: %(reason)s"
                    )
                )
                % {
                    "approver": self.env.user.display_name,
                    "bill": self.display_name,
                    "reason": reason,
                },
                user_id=self.create_uid.id,
            )
        return True
