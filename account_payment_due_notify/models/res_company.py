from datetime import datetime

import pytz
from markupsafe import Markup

from odoo import _, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.tools import formatLang


class ResCompany(models.Model):
    _inherit = "res.company"

    payment_due_notify_enabled = fields.Boolean(
        string="Notify on payment due dates",
        help="Automatically notify the users configured below before a "
        "payable journal item (vendor bill, vendor credit note, or "
        "manual entry with a payable line and a vendor contact) reaches "
        "its due date.",
    )
    payment_due_notify_days_first = fields.Integer(
        string="Days before due date (first notice)",
        default=3,
        help="Number of days before the due date to send the first "
        "notice. 0 means the same day it is due.",
    )
    payment_due_notify_second_enabled = fields.Boolean(
        string="Send a second notice",
        default=True,
        help="If unchecked, only the first notice above is ever sent; "
        "the days configured for the second notice are not evaluated at "
        "all.",
    )
    payment_due_notify_days_second = fields.Integer(
        string="Days before due date (second notice)",
        default=0,
        help="Number of days before the due date to send the second "
        "notice. 0 means the same day it is due. Only used if 'Send a "
        "second notice' is checked.",
    )
    payment_due_notify_time = fields.Float(
        string="Notification time",
        default=9.0,
        help="Approximate local time of day, in the timezone below, at "
        "which notices are sent. The check runs every 30 minutes, so "
        "the actual send time can be up to 30 minutes later.",
    )
    payment_due_notify_tz = fields.Selection(
        _tz_get,
        string="Notification timezone",
        help="Timezone used to evaluate the notification time above. "
        "Never assumed from the server; set it explicitly if it is not "
        "suggested automatically when you enable this feature.",
    )
    payment_due_notify_user_ids = fields.Many2many(
        "res.users",
        "payment_due_notify_res_company_res_users_rel",
        "company_id",
        "user_id",
        string="Users to notify",
        domain=[("share", "=", False)],
        help="Users notified before a payable journal item becomes due. "
        "This list is global per company; it does not vary by vendor or "
        "journal.",
    )
    payment_due_notify_balance_account_ids = fields.Many2many(
        "account.account",
        "payment_due_notify_res_company_account_rel",
        "company_id",
        "account_id",
        string="Accounts to report balance",
        domain=[("account_type", "=", "asset_cash"), ("active", "=", True)],
        help="Optional accounts (normally of type Bank and Cash) whose "
        "current balance is added at the foot of every notification "
        "email, as a quick reference for whether there are enough funds "
        "to pay. Leave empty to not include any balance information.",
    )

    def _get_payment_due_notify_default_tz(self):
        """Suggest a timezone from the company's country. Returns False
        when the country's zones don't all share the same current UTC
        offset (e.g. the US, Brazil, Russia): unlike Argentina, whose many
        IANA zone names are all -03:00 today, those are genuinely
        ambiguous and must be set explicitly instead of guessed.
        """
        self.ensure_one()
        country_code = self.country_id.code
        if not country_code:
            return False
        tz_names = pytz.country_timezones.get(country_code.upper())
        if not tz_names:
            return False
        now = datetime.utcnow()
        offsets = {pytz.timezone(tz_name).utcoffset(now) for tz_name in tz_names}
        return tz_names[0] if len(offsets) == 1 else False

    def _payment_due_notify_in_window(self, now_local):
        """Return True if ``now_local`` (a timezone-aware datetime) falls
        in the same fixed 30-minute bucket as the configured notification
        time, e.g. a 09:00 setting matches any run in [09:00, 09:30).
        """
        self.ensure_one()
        configured_minutes = round(self.payment_due_notify_time * 60)
        now_minutes = now_local.hour * 60 + now_local.minute
        return configured_minutes // 30 == now_minutes // 30

    def _cron_send_payment_due_notices(self):
        companies = self.search([("payment_due_notify_enabled", "=", True)])
        now_utc = pytz.utc.localize(fields.Datetime.now())
        for company in companies:
            if not company.payment_due_notify_tz:
                continue
            now_local = now_utc.astimezone(pytz.timezone(company.payment_due_notify_tz))
            if company._payment_due_notify_in_window(now_local):
                company._send_payment_due_notices(now_local.date())

    def _send_payment_due_notices(self, today):
        self.ensure_one()
        partner_ids = self.payment_due_notify_user_ids.partner_id.ids
        if not partner_ids:
            return
        lines = self.env["account.move.line"].search([
            ("account_id.account_type", "=", "liability_payable"),
            ("reconciled", "=", False),
            ("amount_residual", "!=", 0),
            ("partner_id", "!=", False),
            ("date_maturity", "!=", False),
            ("parent_state", "=", "posted"),
            ("company_id", "=", self.id),
        ])

        first_lines = lines.filtered(
            lambda l: (l.date_maturity - today).days == self.payment_due_notify_days_first
            and not l.payment_due_notice_1_sent
        )
        if first_lines:
            self._send_payment_due_notice_digest(
                first_lines, self.payment_due_notify_days_first, partner_ids
            )
            first_lines.write({"payment_due_notice_1_sent": fields.Datetime.now()})

        if self.payment_due_notify_second_enabled:
            second_lines = lines.filtered(
                lambda l: (l.date_maturity - today).days == self.payment_due_notify_days_second
                and not l.payment_due_notice_2_sent
            )
            if second_lines:
                self._send_payment_due_notice_digest(
                    second_lines, self.payment_due_notify_days_second, partner_ids
                )
                second_lines.write({"payment_due_notice_2_sent": fields.Datetime.now()})

    def _send_payment_due_notice_digest(self, notice_lines, days, partner_ids):
        """Send a single email/notification listing every line in
        ``notice_lines`` (all due in the same number of ``days``), instead
        of one message per document.
        """
        self.ensure_one()
        # The cron runs as base.user_root, whose language is not
        # necessarily the company's: without this, every notice would be
        # composed in whatever language that technical user happens to
        # have (commonly English) regardless of the company's own.
        lang = self.partner_id.lang or self.env.user.lang
        self = self.with_context(lang=lang)
        notice_lines = notice_lines.with_context(lang=lang)
        if days == 0:
            subject = _("Payables due today")
            intro = _("The following payable documents are due today.")
        else:
            subject = _("Payables due in %(days)s days", days=days)
            intro = _(
                "The following payable documents are due in %(days)s days.",
                days=days,
            )
        header_row = Markup(
            "<tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr>"
        ) % (
            _("Vendor"),
            _("Document"),
            _("Reference"),
            _("Due date"),
            _("Amount"),
        )
        body_rows = Markup("").join(
            line._get_payment_due_notice_row() for line in notice_lines
        )
        body = Markup("%s<br/><br/><table>%s%s</table>%s") % (
            intro,
            header_row,
            body_rows,
            self._get_payment_due_notify_balance_section(),
        )
        self.env["mail.thread"].message_notify(
            partner_ids=partner_ids, subject=subject, body=body
        )

    def _get_payment_due_notify_balance_section(self):
        self.ensure_one()
        accounts = self.payment_due_notify_balance_account_ids
        if not accounts:
            return Markup("")
        balances = dict(
            self.env["account.move.line"]._read_group(
                [
                    ("account_id", "in", accounts.ids),
                    ("parent_state", "=", "posted"),
                    ("company_id", "=", self.id),
                ],
                ["account_id"],
                ["balance:sum"],
            )
        )
        rows = Markup("").join(
            Markup("<tr><td>%s</td><td>%s</td></tr>")
            % (
                account.display_name,
                formatLang(self.env, balances.get(account, 0.0), currency_obj=self.currency_id),
            )
            for account in accounts
        )
        return Markup("<br/><br/>%s<table>%s</table>") % (
            _("Account balances (for reference):"),
            rows,
        )
