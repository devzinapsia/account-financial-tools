import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize, formataddr
from odoo.tools.mail import email_split_tuples
from odoo.tools.safe_eval import datetime, safe_eval, time

_logger = logging.getLogger(__name__)


def _split_emails(text):
    """Split a free-text list of emails separated by commas or semicolons
    into ``(name, email)`` tuples."""
    return email_split_tuples((text or "").replace(";", ","))


class MailTransactionCcRule(models.Model):
    _name = "mail.transaction.cc.rule"
    _description = "Email copy rule"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        help="The rule applies to documents of this company, regardless of the "
        "company the sending user is working in.",
    )
    type_id = fields.Many2one(
        "mail.transaction.cc.type",
        string="Transaction type",
        required=True,
        ondelete="cascade",
        domain="[('available', '=', True)]",
    )
    model_name = fields.Char(related="type_id.model_name")
    domain = fields.Char(
        string="Additional condition",
        help="Optional filter on the transaction. Leave empty to apply the rule "
        "to every record of the transaction type.",
    )
    type_has_document = fields.Boolean(related="type_id.has_document")
    scope = fields.Selection(
        [
            ("all", "All communication"),
            ("document", "Document sending only"),
        ],
        required=True,
        default="all",
        compute="_compute_scope",
        store=True,
        readonly=False,
        precompute=True,
        help="All communication: document sending, messages sent to the "
        "customer or vendor from the chatter, and forwarding of incoming "
        "emails.\nDocument sending only: sending wizards, background sending "
        "and automatic reminders of the document.",
    )
    cc_emails = fields.Char(
        string="Cc emails",
        help="Several addresses can be separated by commas or semicolons.",
    )
    cc_user_ids = fields.Many2many(
        "res.users",
        "mail_transaction_cc_rule_cc_user_rel",
        "rule_id",
        "user_id",
        string="Cc users",
    )
    cc_group_ids = fields.Many2many(
        "res.groups",
        "mail_transaction_cc_rule_cc_group_rel",
        "rule_id",
        "group_id",
        string="Cc groups",
        help="Members are resolved when the email is sent.",
    )
    include_responsible = fields.Boolean(
        string="Include the responsible",
        help="Add the email of the transaction's responsible user in Cc.",
    )
    responsible_label = fields.Char(
        string="Responsible field",
        compute="_compute_responsible_label",
    )
    bcc_emails = fields.Char(
        string="Bcc emails",
        help="Several addresses can be separated by commas or semicolons.",
    )
    bcc_user_ids = fields.Many2many(
        "res.users",
        "mail_transaction_cc_rule_bcc_user_rel",
        "rule_id",
        "user_id",
        string="Bcc users",
    )
    bcc_group_ids = fields.Many2many(
        "res.groups",
        "mail_transaction_cc_rule_bcc_group_rel",
        "rule_id",
        "group_id",
        string="Bcc groups",
        help="Members are resolved when the email is sent.",
    )

    @api.depends("type_id")
    def _compute_scope(self):
        for rule in self:
            # without a document of its own, only the chatter communication exists
            if not rule.scope or (rule.type_id and not rule.type_id.has_document):
                rule.scope = "all"

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)._force_scope_without_document()

    def write(self, vals):
        res = super().write(vals)
        if "scope" in vals or "type_id" in vals:
            self._force_scope_without_document()
        return res

    def _force_scope_without_document(self):
        without_document = self.filtered(lambda rule: not rule.type_id.has_document and rule.scope != "all")
        if without_document:
            super(MailTransactionCcRule, without_document).write({"scope": "all"})
        return self

    @api.depends("type_id")
    def _compute_responsible_label(self):
        for rule in self:
            cc_type = rule.type_id
            field = cc_type.model_name in self.env and self.env[cc_type.model_name]._fields.get(
                cc_type.responsible_field or ""
            )
            rule.responsible_label = field._description_string(self.env) if field else False

    @api.constrains(
        "name", "cc_emails", "bcc_emails", "cc_user_ids", "bcc_user_ids",
        "cc_group_ids", "bcc_group_ids", "include_responsible",
    )
    def _check_recipients(self):
        for rule in self:
            if not (
                rule.cc_emails or rule.bcc_emails or rule.cc_user_ids or rule.bcc_user_ids
                or rule.cc_group_ids or rule.bcc_group_ids or rule.include_responsible
            ):
                raise ValidationError(self.env._(
                    "The rule %(name)s must have at least one recipient: an email, "
                    "a user, a group or the responsible.",
                    name=rule.name,
                ))
            for text in (rule.cc_emails, rule.bcc_emails):
                if not text:
                    continue
                invalid = [
                    part.strip() for part in text.replace(";", ",").split(",")
                    if part.strip() and not email_normalize(part.strip())
                ]
                if invalid:
                    raise ValidationError(self.env._(
                        "Invalid email address in rule %(name)s: %(emails)s",
                        name=rule.name,
                        emails=", ".join(invalid),
                    ))

    # ------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------

    def _get_eval_context(self):
        return {
            "uid": self.env.uid,
            "user": self.env.user,
            "datetime": datetime,
            "time": time,
            "context_today": datetime.date.today,
        }

    def _matches(self, record):
        """Return True if ``record`` satisfies the rule's additional domain.
        An invalid domain never breaks sending: the rule is skipped."""
        self.ensure_one()
        if not self.domain or self.domain.strip() in ("", "[]"):
            return True
        try:
            domain = safe_eval(self.domain, self._get_eval_context())
            return bool(record.filtered_domain(domain))
        except Exception as error:  # noqa: BLE001
            _logger.warning(
                "Email copy rule %s (id %s) ignored: invalid domain %r (%s)",
                self.name, self.id, self.domain, error,
            )
            return False

    def _get_user_addresses(self, users, groups):
        users = users.with_context(active_test=False) | groups.with_context(
            active_test=False
        ).all_implied_by_ids.with_context(active_test=False).user_ids
        addresses = []
        for user in users:
            if not user.active:
                _logger.info("Email copy rule %s: archived user %s skipped", self.name, user.login)
            elif not user.email_normalized:
                _logger.info("Email copy rule %s: user %s without email skipped", self.name, user.login)
            else:
                addresses.append((user.name, user.email_normalized))
        return addresses

    @api.model
    def _get_matching_rules(self, record, scopes):
        """Return the active rules applying to ``record`` (a single record),
        using the document's company, not the user's active one."""
        if len(record) != 1:
            return self.browse()
        record = record.sudo()
        cc_types = self.env["mail.transaction.cc.type"].sudo().search([("model_name", "=", record._name)])
        cc_types = cc_types.filtered(lambda cc_type: cc_type._filter_records(record))
        if not cc_types:
            return self.browse()
        company = record.company_id if "company_id" in record._fields else self.env.company
        rules = self.sudo().search([
            ("type_id", "in", cc_types.ids),
            ("company_id", "=", (company or self.env.company).id),
            "|", ("scope", "in", list(scopes)), ("type_id.has_document", "=", False),
        ])
        return rules.filtered(lambda rule: rule._matches(record))

    @api.model
    def _get_transaction_types(self, record):
        """Return the transaction types ``record`` belongs to."""
        if len(record) != 1 or not record.id:
            return self.env["mail.transaction.cc.type"]
        cc_types = self.env["mail.transaction.cc.type"].sudo().search([("model_name", "=", record._name)])
        return cc_types.filtered(lambda cc_type: cc_type._filter_records(record.sudo()))

    @api.model
    def _get_override(self, record):
        """Cc / Bcc typed by the user in a sending wizard for ``record``, which
        replace the rules for that sending. None when there is no override."""
        overrides = self.env.context.get("mail_transaction_cc_override") or {}
        if not overrides or not isinstance(overrides, dict):
            return None
        # The chatter post route accepts a context from the browser: only
        # internal users may choose the copies (never portal users or guests,
        # who could otherwise relay messages to arbitrary addresses).
        if not self.env.user._is_internal():
            return None
        override = overrides.get("%s,%s" % (record._name, record.id))
        if not isinstance(override, dict):
            return None
        return {"cc": str(override.get("cc") or ""), "bcc": str(override.get("bcc") or "")}

    @api.model
    def _resolve_recipients(self, record, document=False, exclude_emails=()):
        """Resolve the Cc / Bcc addresses for ``record``.

        :param bool document: True when the email is the sending of the
          document itself (both scopes apply), False for any other
          communication (only "all" rules apply);
        :param exclude_emails: normalized emails already in "To", removed
          from Cc and Bcc;
        :return: dict with ``cc`` and ``bcc`` lists of formatted addresses,
          or an empty dict when nothing applies.
        """
        cc, bcc = {}, {}
        override = self._get_override(record) if len(record) == 1 else None
        if override is not None:
            # values edited in the sending wizard replace the rules
            for target, text in ((cc, override.get("cc")), (bcc, override.get("bcc"))):
                for name, email in _split_emails(text):
                    normalized = email_normalize(email)
                    if normalized:
                        target.setdefault(normalized, name)
        else:
            scopes = ("all", "document") if document else ("all",)
            rules = self._get_matching_rules(record, scopes)
            if not rules:
                return {}
            record = record.sudo()
            # archived users must be read to be logged as skipped
            for rule in rules.with_context(active_test=False):
                cc_addresses = list(_split_emails(rule.cc_emails))
                cc_addresses += rule._get_user_addresses(rule.cc_user_ids, rule.cc_group_ids)
                if rule.include_responsible:
                    responsible = rule.type_id._get_responsible_user(record)
                    cc_addresses += rule._get_user_addresses(responsible, self.env["res.groups"])
                bcc_addresses = list(_split_emails(rule.bcc_emails))
                bcc_addresses += rule._get_user_addresses(rule.bcc_user_ids, rule.bcc_group_ids)
                for target, addresses in ((cc, cc_addresses), (bcc, bcc_addresses)):
                    for name, email in addresses:
                        normalized = email_normalize(email)
                        if normalized:
                            target.setdefault(normalized, name)
        excluded = {email_normalize(email) for email in exclude_emails if email}
        cc = {email: name for email, name in cc.items() if email not in excluded}
        bcc = {email: name for email, name in bcc.items() if email not in excluded and email not in cc}
        if not cc and not bcc:
            return {}
        return {
            "cc": [formataddr((name if name != email else "", email)) for email, name in cc.items()],
            "bcc": [formataddr((name if name != email else "", email)) for email, name in bcc.items()],
            "cc_normalized": set(cc),
            "bcc_normalized": set(bcc),
        }

    @api.model
    def _get_preview(self, record, document=False, partners=None):
        """Return the default ``(cc, bcc)`` strings of the sending wizards,
        from the rules, excluding the addresses already in "To"."""
        if len(record) != 1 or not record.id:
            return False, False
        to_emails = [partner.email_normalized for partner in (partners or []) if partner.email_normalized]
        resolved = self.with_context(mail_transaction_cc_override=False)._resolve_recipients(
            record, document=document, exclude_emails=to_emails,
        )
        if not resolved:
            return False, False
        # plain addresses (no display names): easier to edit by hand
        return (
            ", ".join(email_normalize(address) for address in resolved["cc"]) or False,
            ", ".join(email_normalize(address) for address in resolved["bcc"]) or False,
        )

    @api.model
    def get_chatter_copies(self, model, res_id):
        """Copies shown under "To" in the chatter's "Send message" box: the
        rules of the "all communication" scope for that record."""
        result = {"available": False, "cc": "", "bcc": ""}
        if not self.env.user._is_internal() or model not in self.env or not res_id:
            return result
        record = self.env[model].browse(res_id).exists()
        if not record or not self._get_transaction_types(record):
            return result
        record.check_access("read")
        cc, bcc = self._get_preview(record, document=False)
        return {"available": True, "cc": cc or "", "bcc": bcc or ""}

    @api.model
    def _check_wizard_emails(self, *texts):
        """Raise if an address typed in a sending wizard is invalid."""
        invalid = [
            part.strip()
            for text in texts if text and '"' not in text
            for part in text.replace(";", ",").split(",")
            if part.strip() and not email_normalize(part.strip())
        ]
        if invalid:
            raise ValidationError(self.env._("Invalid email address: %(emails)s", emails=", ".join(invalid)))

    @api.model
    def _get_override_context(self, record, cc, bcc):
        overrides = dict(self.env.context.get("mail_transaction_cc_override") or {})
        overrides["%s,%s" % (record._name, record.id)] = {"cc": cc or "", "bcc": bcc or ""}
        return {"mail_transaction_cc_override": overrides}
