from datetime import datetime, timedelta

import pytz

from odoo import Command, fields
from odoo.tests import tagged

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

    def test_first_notice_sent_as_single_digest_and_not_duplicated(self):
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)
        self.assertTrue(line.payment_due_notice_1_sent)
        self.assertFalse(line.payment_due_notice_2_sent)

        messages = self._get_notify_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages.subject, "Payables due in 3 days")
        self.assertIn("Journal Entry", messages.body)

        # Running again must not send a second, duplicate message.
        self.company._send_payment_due_notices(today)
        self.assertEqual(len(self._get_notify_messages()), 1)

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
        self.assertEqual(message.subject, "Payables due in 3 days")

    def test_multiple_documents_batched_into_one_message(self):
        today = fields.Date.today()
        move_1, line_1 = self._create_payable_bill(today + timedelta(days=3))
        move_2, line_2 = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)

        self.assertTrue(line_1.payment_due_notice_1_sent)
        self.assertTrue(line_2.payment_due_notice_1_sent)
        messages = self._get_notify_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages.body.count("Journal Entry"), 2)

    def test_second_notice_skipped_when_disabled(self):
        self.company.payment_due_notify_second_enabled = False
        today = fields.Date.today()
        move, line = self._create_payable_bill(today)
        self.company._send_payment_due_notices(today)
        self.assertFalse(line.payment_due_notice_2_sent)
        self.assertFalse(self._get_notify_messages())

    def test_second_notice_sent_when_enabled(self):
        today = fields.Date.today()
        move, line = self._create_payable_bill(today)
        self.company._send_payment_due_notices(today)
        self.assertTrue(line.payment_due_notice_2_sent)
        self.assertFalse(line.payment_due_notice_1_sent)
        self.assertEqual(self._get_notify_messages().subject, "Payables due today")

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
        self.assertFalse(line.payment_due_notice_1_sent)

    def test_balance_section_included_when_configured(self):
        bank_account = self.company_data["default_journal_bank"].default_account_id
        self.company.payment_due_notify_balance_account_ids = [Command.set([bank_account.id])]
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)

        message = self._get_notify_messages()
        self.assertIn("Account balances", message.body)
        self.assertIn(bank_account.display_name, message.body)

    def test_balance_section_omitted_when_not_configured(self):
        today = fields.Date.today()
        move, line = self._create_payable_bill(today + timedelta(days=3))
        self.company._send_payment_due_notices(today)
        message = self._get_notify_messages()
        self.assertNotIn("Account balances", message.body)
