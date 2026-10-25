from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.mail.tests.common import MockEmail


@tagged("post_install", "-at_install")
class TestMailTransactionCc(AccountTestInvoicingCommon, MockEmail):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.company_data["company"]
        cls.company.email = "company@test.example.com"

        cls.customer = cls.env["res.partner"].create({
            "name": "Customer",
            "email": "customer@test.example.com",
        })
        cls.vendor = cls.env["res.partner"].create({
            "name": "Vendor",
            "email": "vendor@test.example.com",
        })
        cls.cc_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Cc User",
            "login": "mtcc_cc_user",
            "email": "cc.user@test.example.com",
            "notification_type": "email",
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
        })
        cls.salesman = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Salesman",
            "login": "mtcc_salesman",
            "email": "salesman@test.example.com",
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
        })
        cls.type_invoice = cls.env.ref("mail_transaction_cc.type_customer_invoice")
        cls.type_receipt = cls.env.ref("mail_transaction_cc.type_receipt")
        cls.type_payment_order = cls.env.ref("mail_transaction_cc.type_payment_order")
        cls.Rule = cls.env["mail.transaction.cc.rule"]

        cls.invoice = cls.init_invoice("out_invoice", partner=cls.customer, amounts=[100], post=True)
        cls.invoice.invoice_user_id = cls.salesman

    def _create_rule(self, **values):
        return self.Rule.create({
            "name": "Test rule",
            "company_id": self.company.id,
            "type_id": self.type_invoice.id,
            **values,
        })

    def _smtp_emails_to(self, email):
        return [
            sent for sent in self.emails
            if email in (sent["msg_to"] or "")
        ]

    def _post_to_customer(self, record, partner, **kwargs):
        return record.message_post(
            body="Hello",
            partner_ids=partner.ids,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            **kwargs,
        )

    # ------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------

    def test_rule_requires_recipients(self):
        with self.assertRaises(ValidationError):
            self._create_rule()

    def test_rule_invalid_email(self):
        with self.assertRaises(ValidationError):
            self._create_rule(cc_emails="good@test.example.com; not-an-email")

    def test_type_availability(self):
        self.assertTrue(self.type_invoice.available)
        self.assertTrue(self.type_receipt.available)
        purchase_type = self.env.ref("mail_transaction_cc.type_purchase")
        self.assertEqual(purchase_type.available, "purchase.order" in self.env)
        available = self.env["mail.transaction.cc.type"].search([("available", "=", True)])
        self.assertIn(self.type_invoice, available)
        self.assertEqual(purchase_type in available, "purchase.order" in self.env)

    # ------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------

    def test_resolution_union_and_dedup(self):
        self._create_rule(
            cc_emails="admin@test.example.com; customer@test.example.com",
            bcc_emails="admin@test.example.com, audit@test.example.com",
            include_responsible=True,
        )
        self._create_rule(name="Second", cc_user_ids=[Command.set(self.cc_user.ids)])
        resolved = self.Rule._resolve_recipients(
            self.invoice, document=True, exclude_emails=["customer@test.example.com"],
        )
        self.assertEqual(
            resolved["cc_normalized"],
            {"admin@test.example.com", "salesman@test.example.com", "cc.user@test.example.com"},
        )
        # address both in Cc and Bcc stays in Cc only; To address is removed
        self.assertEqual(resolved["bcc_normalized"], {"audit@test.example.com"})

    def test_resolution_skips_archived_and_emailless_users(self):
        no_email_user = self.cc_user.copy({"login": "mtcc_no_email", "email": False})
        archived_user = self.cc_user.copy({"login": "mtcc_archived", "email": "archived@test.example.com"})
        archived_user.active = False
        self._create_rule(
            cc_emails="admin@test.example.com",
            cc_user_ids=[Command.set((no_email_user | archived_user).ids)],
        )
        resolved = self.Rule._resolve_recipients(self.invoice, document=True)
        self.assertEqual(resolved["cc_normalized"], {"admin@test.example.com"})

    def test_resolution_group_members(self):
        group = self.env["res.groups"].create({"name": "Email copy test group"})
        self._create_rule(bcc_group_ids=[Command.set(group.ids)])
        self.assertFalse(self.Rule._resolve_recipients(self.invoice, document=True))
        # members resolved at sending time
        group.user_ids = [Command.link(self.cc_user.id)]
        resolved = self.Rule._resolve_recipients(self.invoice, document=True)
        self.assertEqual(resolved["bcc_normalized"], {"cc.user@test.example.com"})

    @mute_logger("odoo.addons.mail_transaction_cc.models.mail_transaction_cc_rule")
    def test_resolution_invalid_domain_ignored(self):
        self._create_rule(cc_emails="broken@test.example.com", domain="[('not_a_field', '=', 1)]")
        self._create_rule(name="Ok", cc_emails="ok@test.example.com", domain="[('amount_total', '>', 50)]")
        self._create_rule(name="No match", cc_emails="nomatch@test.example.com", domain="[('amount_total', '>', 5000)]")
        resolved = self.Rule._resolve_recipients(self.invoice, document=True)
        self.assertEqual(resolved["cc_normalized"], {"ok@test.example.com"})

    def test_resolution_document_company(self):
        other_company = self.setup_other_company()["company"]
        self._create_rule(company_id=other_company.id, cc_emails="other@test.example.com")
        self._create_rule(name="Own", cc_emails="own@test.example.com")
        # the invoice's company rules apply, even when working in the other company
        resolved = self.Rule.with_company(other_company)._resolve_recipients(self.invoice, document=True)
        self.assertEqual(resolved["cc_normalized"], {"own@test.example.com"})

    def test_resolution_scope(self):
        self._create_rule(cc_emails="doc@test.example.com", scope="document")
        self.assertTrue(self.Rule._resolve_recipients(self.invoice, document=True))
        self.assertFalse(self.Rule._resolve_recipients(self.invoice, document=False))

    def test_resolution_excluded_records(self):
        self._create_rule(cc_emails="admin@test.example.com")
        entry = self.env["account.move"].create({"move_type": "entry", "partner_id": self.customer.id})
        self.assertFalse(self.Rule._resolve_recipients(entry, document=True))
        self.assertFalse(self.Rule._resolve_recipients(self.customer, document=True))

    def test_resolution_internal_transfer_excluded(self):
        self.Rule.create({
            "name": "Receipts",
            "company_id": self.company.id,
            "type_id": self.type_receipt.id,
            "cc_emails": "treasury@test.example.com",
        })
        receipt = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.customer.id,
            "amount": 10,
        })
        transfer = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.company.partner_id.id,
            "amount": 10,
        })
        self.assertTrue(self.Rule._resolve_recipients(receipt, document=True))
        self.assertFalse(self.Rule._resolve_recipients(transfer, document=True))

    def test_resolution_without_rule_access(self):
        self._create_rule(cc_emails="admin@test.example.com")
        # a billing user cannot write rules but still gets them applied
        resolved = self.Rule.with_user(self.salesman)._resolve_recipients(
            self.invoice.with_user(self.salesman), document=True,
        )
        self.assertEqual(resolved["cc_normalized"], {"admin@test.example.com"})

    # ------------------------------------------------------------
    # Outgoing emails
    # ------------------------------------------------------------

    def test_invoice_send_wizard_single_email(self):
        """The customer receives ONE email with To: customer and Cc: the rule
        addresses; the Bcc address receives it without appearing in headers."""
        self.invoice.message_subscribe(partner_ids=self.cc_user.partner_id.ids)
        self._create_rule(
            cc_emails="admin@test.example.com",
            cc_user_ids=[Command.set(self.cc_user.ids)],
            bcc_emails="audit@test.example.com",
        )
        wizard = self.env["account.move.send.wizard"].with_context(
            active_model="account.move", active_ids=self.invoice.ids,
        ).create({"sending_methods": ["email"]})
        with self.mock_mail_gateway():
            wizard.action_send_and_print()

        customer_emails = self._smtp_emails_to("customer@test.example.com")
        self.assertEqual(len(customer_emails), 1)
        sent = customer_emails[0]
        self.assertIn("admin@test.example.com", sent["msg_cc"])
        self.assertIn("cc.user@test.example.com", sent["msg_cc"])
        self.assertIn("audit@test.example.com", sent["smtp_to_list"])
        self.assertNotIn("audit@test.example.com", sent["message"])
        self.assertNotIn("Bcc:", sent["message"])
        # no separate email for the Cc addresses, nor a second notification
        # for the internal follower already in Cc
        for sent_email in self.emails:
            if sent_email is not sent:
                self.assertNotIn("cc.user@test.example.com", sent_email["smtp_to_list"])
                self.assertNotIn("admin@test.example.com", sent_email["smtp_to_list"])
        # Cc addresses visible in the message delivery information
        message = self.invoice.message_ids.filtered(lambda m: m.message_type == "comment")[:1]
        self.assertIn(
            "admin@test.example.com",
            message.notification_ids.mapped("mail_email_address"),
        )
        self.assertNotIn(
            "audit@test.example.com",
            message.notification_ids.mapped("mail_email_address"),
        )

    def test_chatter_message_scope(self):
        self._create_rule(cc_emails="all@test.example.com", scope="all")
        self._create_rule(name="Doc", cc_emails="doc@test.example.com", scope="document")
        with self.mock_mail_gateway():
            self._post_to_customer(self.invoice, self.customer)
        sent = self._smtp_emails_to("customer@test.example.com")
        self.assertEqual(len(sent), 1)
        self.assertIn("all@test.example.com", sent[0]["msg_cc"])
        self.assertNotIn("doc@test.example.com", sent[0]["msg_cc"])

    def test_no_cc_on_notes_and_automatic_messages(self):
        self._create_rule(cc_emails="all@test.example.com")
        self.invoice.message_subscribe(partner_ids=self.customer.ids)
        with self.mock_mail_gateway():
            self.invoice.message_post(body="Note", message_type="comment", subtype_xmlid="mail.mt_note")
            self.invoice.message_post(body="Automatic", subtype_xmlid="mail.mt_comment")
        for sent in self.emails:
            self.assertFalse(sent["msg_cc"])
            self.assertNotIn("all@test.example.com", sent["smtp_to_list"])

    def test_no_cc_from_partner(self):
        self._create_rule(cc_emails="all@test.example.com")
        with self.mock_mail_gateway():
            self._post_to_customer(self.customer, self.customer)
        for sent in self.emails:
            self.assertNotIn("all@test.example.com", sent["smtp_to_list"])

    def test_receipt_composer_template(self):
        self.Rule.create({
            "name": "Receipts",
            "company_id": self.company.id,
            "type_id": self.type_receipt.id,
            "cc_emails": "treasury@test.example.com",
            "scope": "document",
        })
        receipt = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.customer.id,
            "amount": 10,
        })
        receipt.action_post()
        template = self.env.ref("account.mail_template_data_payment_receipt")
        composer = self.env["mail.compose.message"].with_context(
            default_composition_mode="comment",
            default_model="account.payment",
            default_res_ids=receipt.ids,
            default_template_id=template.id,
        ).create({})
        with self.mock_mail_gateway():
            composer._action_send_mail()
        sent = self._smtp_emails_to("customer@test.example.com")
        self.assertEqual(len(sent), 1)
        self.assertIn("treasury@test.example.com", sent[0]["msg_cc"])

    def test_receipt_mass_mail(self):
        self.Rule.create({
            "name": "Receipts",
            "company_id": self.company.id,
            "type_id": self.type_receipt.id,
            "cc_emails": "treasury@test.example.com",
            "bcc_emails": "audit@test.example.com",
        })
        receipts = self.env["account.payment"].create([{
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": partner.id,
            "amount": 10,
        } for partner in (self.customer, self.vendor)])
        receipts.action_post()
        template = self.env.ref("account.mail_template_data_payment_receipt")
        composer = self.env["mail.compose.message"].with_context(
            default_composition_mode="mass_mail",
            default_model="account.payment",
            default_res_ids=receipts.ids,
            default_template_id=template.id,
        ).create({})
        with self.mock_mail_gateway():
            composer._action_send_mail()
        for email in ("customer@test.example.com", "vendor@test.example.com"):
            sent = self._smtp_emails_to(email)
            self.assertEqual(len(sent), 1)
            self.assertIn("treasury@test.example.com", sent[0]["msg_cc"])
            self.assertIn("audit@test.example.com", sent[0]["smtp_to_list"])
            self.assertNotIn("audit@test.example.com", sent[0]["message"])

    def test_purchase_when_installed(self):
        """Purchase is not a dependency: only tested when it is installed."""
        if "purchase.order" not in self.env:
            self.skipTest("Purchase is not installed")
        self.Rule.create({
            "name": "Purchases",
            "company_id": self.company.id,
            "type_id": self.env.ref("mail_transaction_cc.type_purchase").id,
            "cc_emails": "purchasing@test.example.com",
            "scope": "document",
        })
        order = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "order_line": [Command.create({"product_id": self.product_a.id, "product_qty": 1})],
        })
        # RFQ sending (composer with template)
        composer = self.env["mail.compose.message"].with_context(
            default_composition_mode="comment",
            default_model="purchase.order",
            default_res_ids=order.ids,
            default_template_id=self.env.ref("purchase.email_template_edi_purchase").id,
        ).create({})
        with self.mock_mail_gateway():
            composer._action_send_mail()
        sent = self._smtp_emails_to("vendor@test.example.com")
        self.assertEqual(len(sent), 1)
        self.assertIn("purchasing@test.example.com", sent[0]["msg_cc"])
        # automatic receipt reminder (posted as a "notification" from a template)
        with self.mock_mail_gateway():
            order.message_post_with_source(
                self.env.ref("purchase.email_template_edi_purchase_reminder"),
                subtype_xmlid="mail.mt_comment",
            )
        sent = self._smtp_emails_to("vendor@test.example.com")
        self.assertEqual(len(sent), 1)
        self.assertIn("purchasing@test.example.com", sent[0]["msg_cc"])

    # ------------------------------------------------------------
    # Incoming emails
    # ------------------------------------------------------------

    def test_incoming_email_forward(self):
        self._create_rule(
            cc_emails="admin@test.example.com",
            bcc_emails="audit@test.example.com",
        )
        with self.mock_mail_gateway():
            self.invoice.message_post(
                body="Reply from customer",
                author_id=self.customer.id,
                email_from=self.customer.email,
                message_type="email",
                subtype_xmlid="mail.mt_comment",
                incoming_email_cc="already@test.example.com",
            )
        forwarded = self._smtp_emails_to("admin@test.example.com")
        self.assertEqual(len(forwarded), 1)
        self.assertIn("audit@test.example.com", forwarded[0]["smtp_to_list"])
        self.assertNotIn("audit@test.example.com", forwarded[0]["message"])
        self.assertIn("Reply from customer", forwarded[0]["message"])

    def test_incoming_email_bcc_only_not_exposed(self):
        self._create_rule(bcc_emails="audit1@test.example.com, audit2@test.example.com")
        with self.mock_mail_gateway():
            self.invoice.message_post(
                body="Reply", author_id=self.customer.id, email_from=self.customer.email,
                message_type="email", subtype_xmlid="mail.mt_comment",
            )
        for email in ("audit1@test.example.com", "audit2@test.example.com"):
            sent = [s for s in self.emails if email in s["smtp_to_list"]]
            self.assertEqual(len(sent), 1)
            other = "audit2" if email.startswith("audit1") else "audit1"
            self.assertNotIn(other, sent[0]["message"])

    def test_incoming_email_document_scope_not_forwarded(self):
        self._create_rule(cc_emails="admin@test.example.com", scope="document")
        with self.mock_mail_gateway():
            self.invoice.message_post(
                body="Reply", author_id=self.customer.id, email_from=self.customer.email,
                message_type="email", subtype_xmlid="mail.mt_comment",
            )
        self.assertFalse(self._smtp_emails_to("admin@test.example.com"))
