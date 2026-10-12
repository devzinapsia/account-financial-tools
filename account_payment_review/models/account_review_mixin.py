from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools import format_datetime, plaintext2html

REVIEW_STATE_SELECTION = [
    ("not_required", "Not required"),
    ("pending", "Pending review"),
    ("reviewed", "Reviewed"),
    ("observed", "With observations"),
    ("answered", "Answered"),
]

# Decisions a reviewer can record through the review wizard.
REVIEW_RESULTS = ("reviewed", "observed", "not_required")

# Fields only this mixin's own methods may write (always as superuser, after
# checking the acting user's rights): see _review_check_protected_vals().
REVIEW_PROTECTED_FIELDS = frozenset(
    {
        "review_state",
        "review_user_id",
        "review_date",
        "review_comment",
        "review_answer",
        "review_issuer_id",
    }
)


class AccountReviewMixin(models.AbstractModel):
    """Post-confirmation review of a document, as an internal control layer
    that never touches the document's own workflow or accounting data: a
    reviewer signs the document off as reviewed, or leaves observations the
    issuer answers.

    The inheriting model must also inherit mail.thread and
    mail.activity.mixin, and implement the ``_review_*`` hooks marked as
    such below.
    """

    _name = "account.review.mixin"
    _description = "Post-confirmation review"

    review_state = fields.Selection(
        selection=REVIEW_STATE_SELECTION,
        string="Review status",
        readonly=True,
        tracking=True,
        copy=False,
        index=True,
        help="Empty until the document is confirmed. Set to 'Pending review' "
        "or 'Not required' on confirmation, depending on the review settings.",
    )
    review_user_id = fields.Many2one(
        "res.users",
        string="Reviewer",
        readonly=True,
        copy=False,
        index="btree_not_null",
        help="User who recorded the last review decision.",
    )
    review_date = fields.Datetime(
        string="Review date",
        readonly=True,
        copy=False,
    )
    review_comment = fields.Text(
        string="Review comment",
        readonly=True,
        copy=False,
        help="Comment left by the reviewer on the last review.",
    )
    review_answer = fields.Text(
        string="Answer to observation",
        readonly=True,
        copy=False,
        help="Last answer given by the issuer to the reviewer's observations.",
    )
    review_issuer_id = fields.Many2one(
        "res.users",
        string="Issued by",
        readonly=True,
        copy=False,
        index="btree_not_null",
        help="User who confirmed the document. Observations are assigned to "
        "this user, who can't review the document themselves.",
    )
    review_is_reviewable = fields.Boolean(
        string="Reviewable",
        compute="_compute_review_is_reviewable",
        search="_search_review_is_reviewable",
    )

    # ------------------------------------------------------------------
    # Hooks to implement on the inheriting model
    # ------------------------------------------------------------------

    def _review_reviewable_domain(self):
        """Domain of the documents that can be reviewed at all, e.g.
        confirmed vendor payments. Hook: must be implemented."""
        raise NotImplementedError()

    def _review_reviewer_group(self):
        """XML id of the group allowed to review. Hook: must be implemented."""
        raise NotImplementedError()

    def _review_answer_group(self):
        """XML id of the group allowed to answer observations, besides the
        document's own issuer. Hook: must be implemented."""
        raise NotImplementedError()

    def _review_subtype_xmlid(self):
        """XML id of the internal subtype review messages are posted with."""
        raise NotImplementedError()

    def _review_observation_activity_xmlid(self):
        """XML id of the activity type assigned to the issuer on observations."""
        raise NotImplementedError()

    def _review_answer_activity_xmlid(self):
        """XML id of the activity type assigned to the reviewer on answers."""
        raise NotImplementedError()

    def _review_answer_days(self):
        """Days the issuer has to answer an observation."""
        return 3

    def _review_observation_hint(self):
        """How the issuer answers, appended to the observation activity."""
        return _(
            "To answer, mark this activity as done and write your answer, "
            "or use the 'Answer observations' button of the document."
        )

    def _review_answer_hint(self):
        """How the reviewer closes the review, appended to the answer activity."""
        return _(
            "Marking this activity as done signs the document off as "
            "reviewed. To record new observations instead, use the 'Mark "
            "as reviewed' button of the document."
        )

    def _review_initial_state(self):
        """Review status a document gets when it's confirmed: 'pending',
        'not_required', or False to stay out of the review circuit."""
        return "pending"

    # ------------------------------------------------------------------
    # Computes, ORM
    # ------------------------------------------------------------------

    def _compute_review_is_reviewable(self):
        # The inheriting model overrides this just to declare its own
        # @api.depends; the logic stays here, driven by the same domain the
        # search method uses, so both always agree.
        reviewable = self.filtered_domain(self._review_reviewable_domain())
        reviewable.review_is_reviewable = True
        (self - reviewable).review_is_reviewable = False

    def _search_review_is_reviewable(self, operator, value):
        if operator not in ("in", "not in"):
            return NotImplemented
        wanted = {bool(v) for v in value}
        if operator == "not in":
            wanted = {True, False} - wanted
        if wanted == {True, False}:
            return Domain.TRUE
        if not wanted:
            return Domain.FALSE
        domain = Domain(self._review_reviewable_domain())
        return domain if True in wanted else ~domain

    def _review_check_protected_vals(self, vals_list):
        """Review fields are only ever written by this mixin's own methods,
        as superuser and after checking rights: block every other path
        (list multi-edit, import, direct RPC calls), the same way core
        protects account.move's own "checked" flag."""
        if self.env.su:
            return
        for vals in vals_list:
            if REVIEW_PROTECTED_FIELDS.intersection(vals):
                raise AccessError(_("Review fields can only be changed through the review actions."))

    @api.model_create_multi
    def create(self, vals_list):
        self._review_check_protected_vals(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._review_check_protected_vals([vals])
        return super().write(vals)

    # ------------------------------------------------------------------
    # Review workflow
    # ------------------------------------------------------------------

    def _review_write(self, vals):
        # Superuser on purpose: a reviewer only needs read access to the
        # document (e.g. a partner with a read-only accounting profile), and
        # the rights are checked explicitly before calling this. The acting
        # user (and thus the tracking author) stays the real one.
        return self.sudo().write(vals)

    def _review_classify_on_confirm(self):
        """Give a just-confirmed document its initial review status. Only
        documents with no review status yet: a decision already recorded on
        it (e.g. before it was reset and confirmed again) is kept."""
        for record in self.filtered(lambda r: r.review_is_reviewable and not r.review_state):
            state = record._review_initial_state()
            if state:
                # No tracking: one message per confirmation would only add
                # noise to the chatter, the status is visible on the record.
                record.sudo().with_context(tracking_disable=True).write({"review_state": state})

    def _review_check_can_review(self):
        if not self.env.user.has_group(self._review_reviewer_group()):
            raise AccessError(_("Only payment reviewers can review payments."))
        self.check_access("read")
        not_reviewable = self.filtered(lambda r: not r.review_is_reviewable)
        if not_reviewable:
            raise UserError(
                _(
                    "Only confirmed vendor payments can be reviewed. These can't: %s",
                    ", ".join(not_reviewable.mapped("display_name")),
                )
            )
        own = self.filtered(lambda r: self.env.user in (r.review_issuer_id | r.create_uid))
        if own:
            raise UserError(
                _(
                    "You can't review payments you registered or confirmed yourself: %s",
                    ", ".join(own.mapped("display_name")),
                )
            )

    def _review_get_issuer(self):
        """Internal, active user the observations are assigned to."""
        self.ensure_one()
        for user in (self.review_issuer_id, self.create_uid):
            if user and user.active and not user.share:
                return user
        return self.env["res.users"]

    def _review_headline(self, result):
        values = {
            "user": self.env.user.display_name,
            "date": format_datetime(self.env, fields.Datetime.now()),
        }
        if result == "reviewed":
            return _("Reviewed by %(user)s on %(date)s: OK", **values)
        if result == "observed":
            return _("Reviewed by %(user)s on %(date)s: with observations", **values)
        if result == "not_required":
            return _("Marked as not requiring review by %(user)s on %(date)s", **values)
        return _("%(user)s answered the observations on %(date)s", **values)

    def _review_post(self, headline, label=None, text=None):
        body = Markup("<p><strong>%s</strong></p>") % headline
        if text:
            body += Markup("<p>%s</p>") % label
            body += plaintext2html(text)
        # Internal subtype: review comments are never e-mailed to followers,
        # which may include the vendor itself. Posted as superuser for the
        # same reason as _review_write(), but authored by the acting user:
        # the author is the reviewer's signature.
        self.sudo().message_post(
            body=body,
            message_type="comment",
            subtype_xmlid=self._review_subtype_xmlid(),
            author_id=self.env.user.partner_id.id,
        )

    def _review_clear_activities(self):
        """Remove the pending review activities. Deleted rather than marked
        as done: marking them done posts another chatter message, and the
        decision itself is already logged by _review_post()."""
        self.sudo().activity_unlink(
            [self._review_observation_activity_xmlid(), self._review_answer_activity_xmlid()],
            only_automated=False,
        )

    def _review_schedule(self, activity_xmlid, user, summary, text):
        self.ensure_one()
        deadline = fields.Date.context_today(self) + timedelta(days=self._review_answer_days())
        self.sudo().activity_schedule(
            activity_xmlid,
            date_deadline=deadline,
            summary=summary,
            note=plaintext2html(text),
            user_id=user.id,
        )

    def _review_set_result(self, result, comment=False):
        """Record a reviewer's decision: 'reviewed', 'observed' (comment
        required, assigns an activity to the issuer) or 'not_required'.
        Allowed from any review status, so the reviewer can change their
        mind later on."""
        if result not in REVIEW_RESULTS:
            raise UserError(_("Invalid review result."))
        comment = (comment or "").strip()
        if result == "observed" and not comment:
            raise UserError(_("A comment is required to record observations."))
        self._review_check_can_review()
        now = fields.Datetime.now()
        for record in self:
            record._review_write(
                {
                    "review_state": result,
                    "review_user_id": self.env.user.id,
                    "review_date": now,
                    "review_comment": comment or False,
                    "review_answer": False,
                }
            )
            record._review_clear_activities()
            record._review_post(record._review_headline(result), _("Comment:"), comment)
            issuer = record._review_get_issuer()
            if result == "observed" and issuer:
                record_lang = record.with_context(lang=issuer.lang)
                record._review_schedule(
                    record._review_observation_activity_xmlid(),
                    issuer,
                    record_lang.env._("Answer the review observations"),
                    f"{comment}\n\n{record_lang._review_observation_hint()}",
                )
        return True

    def _review_answer(self, answer):
        """The issuer (or any user of the answer group) answers the
        reviewer's observations: sends the document back to the reviewer."""
        answer = (answer or "").strip()
        if not answer:
            raise UserError(_("Please write an answer."))
        self.check_access("read")
        may_answer_any = self.env.user.has_group(self._review_answer_group())
        for record in self:
            if record.review_state != "observed":
                raise UserError(_("%s has no observations to answer.", record.display_name))
            if not may_answer_any and self.env.user not in (record.review_issuer_id | record.create_uid):
                raise AccessError(_("You are not allowed to answer the observations of %s.", record.display_name))
        reviewer_group = self._review_reviewer_group()
        for record in self:
            record._review_write({"review_state": "answered", "review_answer": answer})
            record._review_clear_activities()
            record._review_post(record._review_headline("answered"), _("Answer:"), answer)
            reviewer = record.review_user_id
            if reviewer and reviewer.active and reviewer.has_group(reviewer_group):
                record_lang = record.with_context(lang=reviewer.lang)
                record._review_schedule(
                    record._review_answer_activity_xmlid(),
                    reviewer,
                    record_lang.env._("Review the answer to your observations"),
                    f"{answer}\n\n{record_lang._review_answer_hint()}",
                )
        return True

    def _review_activity_done(self, activity, feedback):
        """Act on a review activity marked as done from the activity itself
        rather than from the document's buttons, so both paths do the same:
        the issuer's activity answers the observations with the feedback,
        the reviewer's one signs the document off as reviewed.

        Returns True when the activity was handled here (and thus already
        removed by the review action), False to let it be marked as done
        normally (e.g. a stale activity whose review moved on meanwhile)."""
        self.ensure_one()
        activity_type = activity.activity_type_id
        if activity_type == self.env.ref(self._review_observation_activity_xmlid(), raise_if_not_found=False):
            if self.review_state != "observed":
                return False
            if not (feedback or "").strip():
                raise UserError(
                    _(
                        "Write your answer to the observations of %s before marking the activity as done.",
                        self.display_name,
                    )
                )
            self._review_answer(feedback)
            return True
        if activity_type == self.env.ref(self._review_answer_activity_xmlid(), raise_if_not_found=False):
            if self.review_state != "answered":
                return False
            self._review_set_result("reviewed", feedback)
            return True
        return False
