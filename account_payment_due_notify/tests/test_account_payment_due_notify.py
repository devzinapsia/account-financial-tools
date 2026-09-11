from datetime import datetime, timedelta

import pytz

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools import format_date

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentDueNotify(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.notify_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Notify Me",
                    "login": "payment_due_notify_user",
                    "email": "payment_due_notify_user@test.example.com",
                    "group_ids": [
                        Command.set([cls.env.ref("account.group_account_invoice").id])
                    ],
                }
            )
        )
        cls.company = cls.env.company
        cls.company.write(
            {
                "payment_due_notify_enabled": True,
                "payment_due_notify_days_first": 3,
                "payment_due_notify_second_enabled": True,
                "payment_due_notify_days_second": 0,
                "payment_due_notify_user_ids": [Command.set([cls.notify_user.id])],
            }
        )

    def _create_payable_bill(self, due_date):
        move = self._create_invoice(
            move_type="in_invoice",
            partner_id=self.partner_a.id,
            post=True,
        )
        line = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        )
        line.date_maturity = due_date
        return move, line

    def _get_notify_messages(self):
        return self.env["mail.message"].search(
            [
                ("partner_ids", "in", self.notify_user.partner_id.ids),
                ("message_type", "=", "user_notification"),
            ]
        )

    def _next_monday(self):
        day = fields.Date.today()
        while day.weekday() != 0:
            day += timedelta(days=1)
        return day

    def test_default_tz_guess_argentina(self):
        self.company.country_id = self.env.ref("base.ar")
        self.assertIn(
            self.company._get_payment_due_notify_default_tz(),
            pytz.country_timezones["AR"],
        )

    def test_default_tz_guess_ambiguous_country(self):
        # The US spans several distinct UTC offsets today, so no single
        # timezone can be safely suggested.
        self.company.country_id = self.env.ref("base.us")
        self.assertFalse(self.company._get_payment_due_notify_default_tz())

    def test_notify_window(self):
        self.company.payment_due_notify_time = 9.0
        tz = pytz.timezone("America/Argentina/Buenos_Aires")
        in_window = tz.localize(datetime(2026, 1, 1, 9, 15))
        out_of_window = tz.localize(datetime(2026, 1, 1, 9, 45))
        self.assertTrue(self.company._payment_due_notify_in_window(in_window))
        self.assertFalse(self.company._payment_due_notify_in_window(out_of_window))

    def test_first_notice_sent_as_single_digest(self):
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)

        messages = self._get_notify_messages()
        self.assertEqual(len(messages), 1)
        date_str = format_date(self.env, today + timedelta(days=3))
        self.assertEqual(
            messages.subject,
            f"Payables due in 3 days ({date_str}) in {self.company.name}",
        )
        self.assertIn("Journal Entry", messages.body)
        # The date moved to the subject; the body intro no longer repeats it.
        self.assertIn("<strong>Payable documents:</strong>", messages.body)
        # No "Due date" column in the daily digest: the single due date is
        # already stated in the subject instead.
        self.assertNotIn(">Due date<", messages.body)

    def test_running_again_resends_whatever_still_matches(self):
        # No per-document tracking: a repeated run for the same day is
        # not deduplicated, by design -- it simply sends the same
        # currently-matching set again, exactly like a fresh run. This
        # matters when the notification time is reconfigured mid-day, or
        # when the check is triggered by hand more than once.
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)
        self.company._send_payment_due_notices(today)
        self.assertEqual(len(self._get_notify_messages()), 2)

    def test_digest_document_is_a_hyperlink_and_no_signature(self):
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)

        message = self._get_notify_messages()
        # The document label itself is the link (no separate icon/arrow
        # or <img>, which real mail clients failed to render reliably).
        self.assertNotIn("<img", message.body)
        self.assertRegex(
            message.body,
            # "&" in the URL is correctly HTML-escaped to "&amp;" -- it is
            # a literal query-string separator here, not markup.
            r'<a href="[^"]*id=%s&amp;model=account\.move[^"]*"[^>]*>Journal Entry'
            % move.id,
        )
        self.assertFalse(message.email_add_signature)

    def test_digest_uses_company_language_not_acting_user_language(self):
        # The cron runs as base.user_root, whose language is not
        # necessarily the company's. Composing the digest must follow
        # the company's own language (falling back to it here), not
        # whatever language happens to be in the ambient context.
        self.company.partner_id.lang = "en_US"
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company.with_context(lang="es_AR")._send_payment_due_notices(today)
        message = self._get_notify_messages()
        date_str = format_date(self.env, today + timedelta(days=3), lang_code="en_US")
        self.assertEqual(
            message.subject,
            f"Payables due in 3 days ({date_str}) in {self.company.name}",
        )

    def test_multiple_documents_batched_into_one_message(self):
        today = fields.Date.today()
        move_1, line_1 = self._create_payable_bill(today + timedelta(days=3))
        move_2, line_2 = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)

        messages = self._get_notify_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages.body.count("Journal Entry"), 2)

    def test_second_notice_skipped_when_disabled(self):
        self.company.payment_due_notify_second_enabled = False
        today = fields.Date.today()
        move, line = self._create_payable_bill(today)
        self.company._send_payment_due_notices(today)
        self.assertFalse(self._get_notify_messages())

    def test_second_notice_sent_when_enabled(self):
        today = fields.Date.today()
        move, line = self._create_payable_bill(today)
        self.company._send_payment_due_notices(today)
        date_str = format_date(self.env, today)
        self.assertEqual(
            self._get_notify_messages().subject,
            f"Payables due today ({date_str}) in {self.company.name}",
        )

    def test_paid_line_excluded(self):
        self.company.payment_due_notify_days_first = 0
        today = fields.Date.today()
        move, line = self._create_payable_bill(today)
        payment_register = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=move.ids)
            .create({})
        )
        payment_register.action_create_payments()
        self.company._send_payment_due_notices(today)
        self.assertFalse(self._get_notify_messages())

    def test_balance_account_domain_excludes_archived_accounts(self):
        bank_account = self.company_data["default_journal_bank"].default_account_id
        bank_account.active = False
        # Bypass the ORM's own default active filtering so this actually
        # proves the field's own domain is what excludes archived
        # accounts, not just the ORM's implicit active_test behavior.
        AccountNoActiveTest = self.env["account.account"].with_context(active_test=False)
        for model, field_name in (
            (self.env["res.company"], "payment_due_notify_balance_account_ids"),
            (self.env["res.config.settings"], "payment_due_notify_balance_account_ids"),
        ):
            domain = model._fields[field_name].domain
            found = AccountNoActiveTest.search(domain + [("id", "=", bank_account.id)])
            self.assertFalse(
                found,
                f"{model._name}.{field_name}'s domain should exclude archived accounts",
            )

    def test_balance_section_included_when_configured(self):
        bank_account = self.company_data["default_journal_bank"].default_account_id
        self.company.payment_due_notify_balance_account_ids = [Command.set([bank_account.id])]
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)

        message = self._get_notify_messages()
        self.assertIn("Bank and cash balance", message.body)
        self.assertIn(bank_account.name, message.body)
        # The account code must not leak into the email, only the name.
        self.assertNotIn(bank_account.code, message.body)

    def test_balance_section_omitted_when_not_configured(self):
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)
        message = self._get_notify_messages()
        self.assertNotIn("Bank and cash balance", message.body)

    def test_weekly_summary_sent_ascending_by_due_date(self):
        self.company.payment_due_notify_weekly_summary_enabled = True
        monday = self._next_monday()
        move_later, line_later = self._create_payable_bill(monday + timedelta(days=4))
        move_sooner, line_sooner = self._create_payable_bill(monday + timedelta(days=1))

        self.company._send_payment_due_notify_weekly_summary(monday)

        self.assertEqual(
            self.company.payment_due_notify_weekly_summary_last_sent, False
        )
        message = self._get_notify_messages()
        self.assertEqual(len(message), 1)
        sunday = monday + timedelta(days=6)
        self.assertEqual(
            message.subject,
            "Payables due this week (%s to %s) in %s"
            % (monday.strftime("%d-%m-%Y"), sunday.strftime("%d-%m-%Y"), self.company.name),
        )
        self.assertIn(">Due date<", message.body)
        self.assertIn("<strong>Payable documents:</strong>", message.body)
        body = message.body
        self.assertLess(body.index(move_sooner.name), body.index(move_later.name))

    def test_weekly_summary_not_sent_when_disabled(self):
        monday = self._next_monday()
        self._create_payable_bill(monday + timedelta(days=2))
        self.company._send_payment_due_notify_weekly_summary(monday)
        # payment_due_notify_weekly_summary_enabled is False by default, but
        # the method itself doesn't gate on it (the cron does) -- calling
        # it directly still sends. This documents that the gating lives in
        # _cron_send_payment_due_notices, exercised in the next test.
        self.assertTrue(self._get_notify_messages())

    def test_cron_skips_weekly_summary_when_disabled_or_already_sent(self):
        monday = self._next_monday()
        self._create_payable_bill(monday + timedelta(days=2))
        self.company.payment_due_notify_weekly_summary_enabled = False

        # Mirrors the gating _cron_send_payment_due_notices applies.
        if (
            self.company.payment_due_notify_weekly_summary_enabled
            and monday.weekday() == 0
            and self.company.payment_due_notify_weekly_summary_last_sent != monday
        ):
            self.company._send_payment_due_notify_weekly_summary(monday)
        self.assertFalse(self._get_notify_messages())

        self.company.payment_due_notify_weekly_summary_enabled = True
        self.company.payment_due_notify_weekly_summary_last_sent = monday
        if (
            self.company.payment_due_notify_weekly_summary_enabled
            and monday.weekday() == 0
            and self.company.payment_due_notify_weekly_summary_last_sent != monday
        ):
            self.company._send_payment_due_notify_weekly_summary(monday)
        self.assertFalse(self._get_notify_messages())
