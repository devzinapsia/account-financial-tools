from markupsafe import Markup

from odoo import _, api, fields, models, modules
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

    def _sync_authorization_state_with_match(self):
        """Keep authorization_state accurate for draft vendor bills that
        haven't had an explicit authorization decision made on them yet: it
        must read "To authorize" as soon as the bill matches a policy, not
        stay on the default "Not required" until someone happens to attempt
        action_post() and gets blocked.

        Deliberately skips "authorized"/"rejected": those are decisions a
        person made, not a derived fact, and must never be silently
        overwritten by a recompute of matched_policy_ids (see write()'s own
        handling of a no-longer-valid decision instead).
        """
        for move in self:
            if move.move_type not in VENDOR_BILL_TYPES:
                # E.g. a draft whose type was switched away from a vendor
                # bill: this module never applies to it anymore.
                if move.authorization_state != "not_required":
                    super(AccountMove, move).write(
                        {"authorization_state": "not_required", "authorized_by_id": False}
                    )
                continue
            if move.state != "draft":
                continue
            if move.authorization_state not in ("not_required", "to_authorize"):
                continue
            new_state = "to_authorize" if move.matched_policy_ids else "not_required"
            if move.authorization_state != new_state:
                super(AccountMove, move).write({"authorization_state": new_state})

    def _force_authorization_compute(self):
        # Force matched_policy_ids/pending_authorizer_ids/is_blocked to be
        # computed and flushed right away, instead of leaving them lazily
        # "to compute" until something happens to read them (e.g. opening
        # the bill's form). Search domains on these fields (the "To
        # authorize" / "To authorize by me" filters) are not guaranteed to
        # trigger that lazy computation themselves. Loop instead of reading
        # the fields on `self` directly: field access only works on a single
        # record at a time, but the first access still recomputes the whole
        # pending batch.
        for move in self:
            move.pending_authorizer_ids
            move.is_blocked

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._force_authorization_compute()
        moves._sync_authorization_state_with_match()
        return moves

    def write(self, vals):
        if self.env.context.get(POSTING_CONTEXT_KEY):
            return super().write(vals)

        # If a vendor bill was already authorized (or rejected) and this
        # write touches a field an authorization policy's domain could
        # plausibly key off of (most obviously the lines/amount, but also
        # the vendor, journal, currency, dates or classification), that
        # earlier decision no longer says anything about the bill as it
        # exists now -- someone could otherwise get a small amount
        # authorized, then bump it up before confirming without ever being
        # re-checked, since action_post() trusts an "authorized" bill.
        # Capture who needs to be reset *before* the write changes anything.
        to_reset_on_edit = self.browse()
        if self._get_authorization_sensitive_fields().intersection(vals):
            to_reset_on_edit = self.filtered(
                lambda m: m.move_type in VENDOR_BILL_TYPES
                and m.state == "draft"
                and m.authorization_state in ("authorized", "rejected")
            )
        # A bill authorized, confirmed and then reset to draft must be
        # authorized again before it can be confirmed again: it can be
        # freely edited once back in draft.
        to_reset_on_draft = self.browse()
        if vals.get("state") == "draft":
            to_reset_on_draft = self.filtered(
                lambda m: m.move_type in VENDOR_BILL_TYPES
                and m.state != "draft"
                and m.authorization_state == "authorized"
            )
        previous = {
            move.id: (move.authorization_state, move.authorized_by_id)
            for move in to_reset_on_edit | to_reset_on_draft
        }

        result = super().write(vals)
        if "state" in vals:
            # The policy conditions are usually scoped to draft bills (see
            # the policy's default domain), so a bill going back to draft
            # must be re-evaluated against the live configuration.
            self._refresh_authorization_state()
        else:
            self._force_authorization_compute()

        to_reset = to_reset_on_edit | to_reset_on_draft
        if to_reset:
            # Bypass this same override: the correction write below only
            # touches authorization fields, none of which is
            # authorization-sensitive.
            super(AccountMove, to_reset).write(
                {"authorization_state": "to_authorize", "authorized_by_id": False}
            )
            for move in to_reset:
                previous_state, previous_authorizer = previous[move.id]
                if move in to_reset_on_draft:
                    body = _(
                        "Authorization reset: this vendor bill was reset to "
                        "draft after %s authorized it, so it must be "
                        "authorized again before it can be confirmed.",
                        previous_authorizer.display_name or _("an authorizer"),
                    )
                elif previous_state == "rejected":
                    body = _(
                        "Rejection reset: this vendor bill's data changed "
                        "after it was rejected, so it is pending "
                        "authorization again."
                    )
                else:
                    body = _(
                        "Authorization reset: this vendor bill's data changed "
                        "after %s authorized it, so it must be authorized "
                        "again before it can be confirmed.",
                        previous_authorizer.display_name or _("an authorizer"),
                    )
                move.message_post(body=body)

        self._sync_authorization_state_with_match()
        return result

    def _refresh_authorization_state(self):
        """Force a real recompute of the matching fields against the current
        policy configuration, instead of trusting a possibly stale stored
        value. Editing a policy's conditions (e.g. adding a vendor) does
        not, by itself, invalidate the stored compute on existing draft
        bills, since there is no stored relation to depend on before the
        match is evaluated. Calling this before every authorization-
        sensitive decision keeps those decisions always based on the live
        configuration.
        """
        moves = self.exists()
        if not moves:
            return
        fnames = ["matched_policy_ids", "pending_authorizer_ids", "is_blocked"]
        for fname in fnames:
            self.env.add_to_compute(self._fields[fname], moves)
        moves._recompute_recordset(fnames)
        moves._sync_authorization_state_with_match()

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

    def _mark_authorization_activities_done(self, feedback):
        self.activity_ids.filtered(
            lambda activity: activity.activity_type_id == self.env.ref(ACTIVITY_TYPE_XMLID)
        ).action_feedback(feedback=feedback)

    def _create_authorization_activities(self):
        for move in self:
            if move.is_blocked:
                # Nobody can ever approve it: asking anyone would only
                # suggest that waiting for an approval will help.
                move.message_post(
                    body=_(
                        "This vendor bill is permanently blocked by the "
                        "following policy/policies: %s.",
                        ", ".join(move.matched_policy_ids.filtered("always_block").mapped("name")),
                    )
                )
                continue

            for user in move.pending_authorizer_ids:
                move.activity_schedule(
                    ACTIVITY_TYPE_XMLID,
                    summary=_("Vendor bill authorization requested"),
                    note=_(
                        "%(requester)s requested your authorization to confirm "
                        "vendor bill %(bill)s (%(amount)s %(currency)s) from "
                        "%(partner)s.",
                        requester=self.env.user.display_name,
                        bill=move.display_name,
                        amount=move.amount_total,
                        currency=move.currency_id.name,
                        partner=move.partner_id.display_name,
                    ),
                    user_id=user.id,
                )
            if move.pending_authorizer_ids:
                move.message_post(
                    body=_(
                        "Authorization requested from: %s",
                        ", ".join(move.pending_authorizer_ids.mapped("display_name")),
                    )
                )
            else:
                move.message_post(
                    body=_(
                        "This vendor bill matches an authorization policy with "
                        "no authorized users configured. It cannot be approved "
                        "until a user is added to that policy."
                    )
                )

    def action_post(self):
        self._refresh_authorization_state()

        to_confirm = self.browse()
        blocked_moves = self.browse()
        for move in self:
            if move.move_type not in VENDOR_BILL_TYPES or move.state != "draft":
                to_confirm += move
                continue

            if move.is_blocked:
                # "Always block" wins over everything, including an earlier
                # authorization (e.g. the policy was changed afterwards).
                if move.authorization_state != "to_authorize":
                    move.write({"authorization_state": "to_authorize", "authorized_by_id": False})
                blocked_moves += move
                continue

            if move.authorization_state == "authorized":
                # Already explicitly authorized earlier via
                # action_authorize_bill() (the "Authorize" button), without
                # confirming at that time. That decision stands -- anyone
                # can now confirm, no need to be an authorizer themselves.
                move.message_post(
                    body=_(
                        "Vendor bill confirmed by %(user)s (authorized earlier "
                        "by %(authorized_by)s).",
                        user=self.env.user.display_name,
                        authorized_by=move.authorized_by_id.display_name,
                    )
                )
                to_confirm += move
                continue

            if not move.matched_policy_ids:
                to_confirm += move
            elif self.env.user in move.pending_authorizer_ids:
                move.write({"authorization_state": "authorized", "authorized_by_id": self.env.user.id})
                move._mark_authorization_activities_done(
                    _("Vendor bill authorized by %s.", self.env.user.display_name)
                )
                move.message_post(
                    body=_(
                        "Vendor bill authorized and confirmed directly by %s "
                        "(already an authorized user for a matching policy).",
                        self.env.user.display_name,
                    )
                )
                to_confirm += move
            else:
                if move.authorization_state != "to_authorize":
                    move.write({"authorization_state": "to_authorize"})
                blocked_moves += move
        blocked_moves._create_authorization_activities()

        result = False
        if to_confirm:
            result = super(AccountMove, to_confirm).action_post()

        if blocked_moves and not to_confirm:
            permanently_blocked = blocked_moves.filtered("is_blocked")
            to_authorize = blocked_moves - permanently_blocked

            messages = []
            if permanently_blocked:
                messages.append(permanently_blocked._get_blocked_error_message())
            if to_authorize:
                if len(to_authorize) == 1:
                    messages.append(
                        _(
                            "This vendor bill requires authorization before it "
                            "can be confirmed. An activity has been assigned "
                            "to the authorized user(s)."
                        )
                    )
                else:
                    messages.append(
                        _(
                            "These vendor bills require authorization before "
                            "they can be confirmed: %s. An activity has been "
                            "assigned to the authorized user(s) of each.",
                            ", ".join(to_authorize.mapped("display_name")),
                        )
                    )
            # A UserError raised here would otherwise roll back every write
            # this method just made (authorization_state, the activities,
            # the chatter messages) -- Odoo's RPC dispatcher rolls back the
            # whole request's transaction whenever an exception escapes
            # uncaught. Commit now so the block is actually recorded despite
            # the confirm attempt failing. Skipped under the test runner,
            # where the cursor is a savepoint on a shared per-test
            # transaction that must not be committed.
            if not modules.module.current_test:
                self.env.cr.commit()
            raise UserError("\n\n".join(messages))
        return result

    def _check_vendor_bill_authorization_before_post(self):
        """Safety net for every posting path that doesn't go through
        action_post() (the "Post entries" list action, i.e. the
        validate.account.move wizard; the auto-post cron; third-party
        background posting...): a vendor bill that is blocked, or that
        matches a policy without having been authorized, is never posted.
        Unlike action_post(), this does not create activities nor commit:
        it only refuses.
        """
        moves = self.filtered(lambda m: m.move_type in VENDOR_BILL_TYPES and m.state == "draft")
        if not moves:
            return
        moves._refresh_authorization_state()
        blocked = moves.filtered("is_blocked")
        if blocked:
            raise UserError(blocked._get_blocked_error_message())
        unauthorized = moves.filtered(
            lambda m: m.matched_policy_ids and m.authorization_state != "authorized"
        )
        if unauthorized:
            raise UserError(
                _(
                    "The following vendor bills require authorization before "
                    "they can be confirmed: %s.",
                    ", ".join(unauthorized.mapped("display_name")),
                )
            )

    def _post(self, soft=True):
        if self.env.context.get("move_reverse_cancel"):
            # Full refund / "modify" reversal of an already posted vendor
            # bill: core creates and posts the credit note in one go to
            # cancel the original; it is not a new document to be approved.
            reversals = self.filtered(
                lambda m: m.move_type in VENDOR_BILL_TYPES
                and m.state == "draft"
                and m.authorization_state != "not_required"
            )
            if reversals:
                super(AccountMove, reversals).write({"authorization_state": "not_required"})
        else:
            self._check_vendor_bill_authorization_before_post()
        return super(AccountMove, self.with_context(**{POSTING_CONTEXT_KEY: True}))._post(soft=soft)

    def _check_bill_pending_authorization(self, access_error_message):
        self._refresh_authorization_state()
        for move in self:
            if (
                move.move_type not in VENDOR_BILL_TYPES
                or move.state != "draft"
                or move.authorization_state in ("authorized", "rejected")
            ):
                raise UserError(_("This vendor bill is not pending authorization."))
            if move.is_blocked:
                raise UserError(move._get_blocked_error_message())
            if self.env.user not in move.pending_authorizer_ids:
                raise AccessError(access_error_message)

    def action_authorize_bill(self):
        """Authorize a vendor bill without confirming it. This can be done
        proactively on a draft bill that matches a policy, without anyone
        having to attempt (and be blocked from) confirming it first.
        Confirming is a deliberately separate step (the regular "Confirm"
        button): once authorization_state is 'authorized', action_post()
        lets anyone confirm it, not just an authorized user.
        """
        self._check_bill_pending_authorization(_("You are not allowed to authorize this vendor bill."))
        for move in self:
            move.write({"authorization_state": "authorized", "authorized_by_id": self.env.user.id})
            move._mark_authorization_activities_done(
                _("Vendor bill authorized by %s.", self.env.user.display_name)
            )
            move.message_post(
                body=_(
                    "Vendor bill authorized by %s. Awaiting confirmation.",
                    self.env.user.display_name,
                )
            )
        return True

    def action_authorize_and_confirm_bill(self):
        """Authorize and confirm in a single click. Same checks as
        action_authorize_bill(); the actual authorization is then recorded
        by action_post() itself, through its "the user confirming is an
        authorizer" branch, so the chatter shows a single "authorized and
        confirmed" event instead of two.
        """
        self._check_bill_pending_authorization(_("You are not allowed to authorize this vendor bill."))
        return self.action_post()

    def action_unauthorize_bill(self):
        """Revert an authorized-but-not-yet-confirmed vendor bill back to
        "to_authorize", undoing a mistaken Authorize click. Any user who is
        currently a pending authorizer of the bill can do it, not only the
        one who authorized it. The bill can be authorized again afterwards,
        by the same or a different authorizer, with no restriction.
        """
        self._refresh_authorization_state()
        for move in self:
            if (
                move.move_type not in VENDOR_BILL_TYPES
                or move.state != "draft"
                or move.authorization_state != "authorized"
            ):
                raise UserError(_("This vendor bill is not currently authorized."))
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
        """
        self.ensure_one()
        self._check_bill_pending_authorization(_("You are not allowed to reject this vendor bill."))
        self.write({"authorization_state": "rejected", "authorization_reject_reason": reason})
        self._mark_authorization_activities_done(
            _(
                "Vendor bill rejected by %(user)s.\nReason: %(reason)s",
                user=self.env.user.display_name,
                reason=reason,
            )
        )
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
