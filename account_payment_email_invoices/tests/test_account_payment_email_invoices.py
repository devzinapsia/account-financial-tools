import io
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import Form, new_test_user, tagged
from odoo.tools import human_size
from odoo.tools.pdf import PdfReader, PdfWriter
from odoo.tools.safe_eval import safe_eval

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account_payment_email_invoices.wizard.mail_compose_message import PAYMENT_INVOICE_MARKER


def _pdf_bytes(pages=1):
    writer = PdfWriter()
    for _index in range(pages):
        writer.add_blank_page(width=72, height=72)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


@tagged("post_install", "-at_install")
class TestAccountPaymentEmailInvoices(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang="en_US"))
        cls.env.user.lang = "en_US"
        cls.company = cls.company_data["company"]
        cls.partner_a.email = "partner_a@example.com"
        cls.partner_b.email = "partner_b@example.com"
        cls.template = cls.env.ref("account.mail_template_data_payment_receipt")
        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.purchase_journal = cls.company_data["default_journal_purchase"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_params(self, company=None, payment_order=False, receipt=False, journals=None):
        (company or self.company).write(
            {
                "attach_invoices_on_payment_order": payment_order,
                "attach_invoices_on_receipt": receipt,
                "no_attachment_journal_ids": [Command.set((journals or self.env["account.journal"]).ids)],
            }
        )

    def _invoice(self, amount=1000.0, move_type="out_invoice", partner=None, journal=None, company=None, post=True):
        company = company or self.company
        move = self.env["account.move"].with_company(company).create(
            {
                "move_type": move_type,
                "partner_id": (partner or self.partner_a).id,
                "invoice_date": "2026-01-01",
                "date": "2026-01-01",
                "company_id": company.id,
                "invoice_line_ids": [Command.create({"name": "line", "quantity": 1, "price_unit": amount, "tax_ids": []})],
                **({"journal_id": journal.id} if journal else {}),
            }
        )
        if post:
            move.action_post()
        return move

    def _bill(self, amount=1000.0, move_type="in_invoice", with_pdf=True, **kwargs):
        bill = self._invoice(move_type=move_type, amount=amount, **kwargs)
        if with_pdf:
            attachment = self.env["ir.attachment"].create(
                {
                    "name": "vendor-%s.pdf" % bill.id,
                    "raw": _pdf_bytes(),
                    "mimetype": "application/pdf",
                    "res_model": "account.move",
                    "res_id": bill.id,
                }
            )
            bill.message_main_attachment_id = attachment
        return bill

    def _pay(self, moves, **kwargs):
        return self._register_payment(moves, payment_date="2026-01-02", **kwargs)

    def _composer(self, payments, mode="comment", template=None, **values):
        return (
            self.env["mail.compose.message"]
            .with_context(
                default_model="account.payment",
                default_res_ids=payments.ids,
                default_composition_mode=mode,
                default_template_id=(template or self.template).id,
            )
            .create(values)
        )

    @staticmethod
    def _ours(attachments):
        return attachments.filtered(lambda a: a.description == PAYMENT_INVOICE_MARKER)

    @staticmethod
    def _names(attachments):
        return attachments.sorted("id").mapped("name")

    @staticmethod
    def _file_names(moves):
        return [move._get_payment_email_attachment_name() for move in moves]

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def test_settings_off_same_attachments(self):
        """Both settings off: the email carries exactly the template attachments."""
        self._set_params()
        invoice = self._invoice()
        payment = self._pay(invoice)
        composer = self._composer(payment)
        self.assertEqual(len(composer.attachment_ids), 1, "Only the payment receipt report.")
        self.assertFalse(self._ours(composer.attachment_ids))
        messages = composer._action_send_mail()[1]
        self.assertEqual(self._names(messages.attachment_ids), self._names(composer.attachment_ids))
        self.assertFalse(self._ours(messages.attachment_ids))

    def test_payment_order_setting(self):
        """Payment order setting: vendor bills are added after the receipt; the
        receipt setting has no effect on a payment order."""
        bill_1, bill_2 = self._bill(1000, partner=self.partner_b), self._bill(500, partner=self.partner_b)
        payment = self._pay(bill_1 | bill_2)
        self.assertEqual(payment.payment_type, "outbound")

        self._set_params(receipt=True)
        self.assertFalse(self._ours(self._composer(payment).attachment_ids))

        self._set_params(payment_order=True)
        composer = self._composer(payment)
        receipt = composer.attachment_ids - self._ours(composer.attachment_ids)
        self.assertEqual(len(receipt), 1)
        self.assertEqual(self._names(composer.attachment_ids), receipt.mapped("name") + self._file_names(bill_1 | bill_2))

    def test_receipt_setting(self):
        """Receipt setting: customer invoices are added; the payment order
        setting has no effect on a receipt."""
        invoice_1, invoice_2 = self._invoice(1000), self._invoice(300)
        payment = self._pay(invoice_1 | invoice_2)
        self.assertEqual(payment.payment_type, "inbound")

        self._set_params(payment_order=True)
        self.assertFalse(self._ours(self._composer(payment).attachment_ids))

        self._set_params(receipt=True)
        composer = self._composer(payment)
        self.assertEqual(self._names(self._ours(composer.attachment_ids)), self._file_names(invoice_1 | invoice_2))

    def test_selector_domain(self):
        """The excluded journals selector only offers sales and purchase
        journals of the settings' company."""
        other = self.setup_other_company()["company"]
        domain = safe_eval(
            self.env["res.config.settings"]._fields["no_attachment_journal_ids"].domain,
            {"company_id": self.company.id},
        )
        journals = self.env["account.journal"].search(domain)
        self.assertTrue(journals)
        self.assertEqual(set(journals.mapped("type")), {"sale", "purchase"})
        self.assertEqual(journals.company_id, self.company)
        self.assertFalse(journals & self.env["account.journal"].search([("company_id", "=", other.id)]))
        self.assertIn(self.sale_journal, journals)
        self.assertNotIn(self.company_data["default_journal_bank"], journals)

    # ------------------------------------------------------------------
    # Which documents
    # ------------------------------------------------------------------

    def test_credit_note_in_payment(self):
        """A credit note settled within the payment is attached too."""
        self._set_params(receipt=True)
        invoice = self._invoice(1000)
        credit_note = self._invoice(300, move_type="out_refund")
        payment = self._pay(invoice | credit_note)
        self.assertEqual(payment.amount, 700)
        composer = self._composer(payment)
        self.assertEqual(
            sorted(self._names(self._ours(composer.attachment_ids))), sorted(self._file_names(invoice | credit_note))
        )

    def test_partial_and_several_payments(self):
        """Each email carries the documents of THAT payment, without duplicates:
        partial payment, invoice paid by two payments, payment of two invoices."""
        self._set_params(receipt=True)
        invoice_a, invoice_b = self._invoice(1000), self._invoice(500)
        payment_1 = self._pay(invoice_a, amount=400)
        self.assertEqual(invoice_a.payment_state, "partial")
        payment_2 = self._pay(invoice_a | invoice_b)
        self.assertIn(invoice_a.payment_state, ("in_payment", "paid"))

        names_1 = self._names(self._ours(self._composer(payment_1).attachment_ids))
        names_2 = self._names(self._ours(self._composer(payment_2).attachment_ids))
        self.assertEqual(names_1, self._file_names(invoice_a))
        self.assertEqual(sorted(names_2), sorted(self._file_names(invoice_a | invoice_b)))
        self.assertEqual(len(names_2), len(set(names_2)))

    def test_excluded_journals(self):
        """Documents of an excluded journal are not attached."""
        go_live_journal = self.env["account.journal"].create(
            {"name": "Go Live adjustments", "type": "sale", "code": "GOL", "company_id": self.company.id}
        )
        invoice = self._invoice(1000)
        adjustment = self._invoice(500, journal=go_live_journal)
        payment = self._pay(invoice | adjustment)
        self._set_params(receipt=True, journals=go_live_journal)
        self.assertEqual(self._names(self._ours(self._composer(payment).attachment_ids)), self._file_names(invoice))

    def test_draft_and_cancelled_not_attached(self):
        """Only posted documents are attached."""
        self._set_params(receipt=True)
        invoice = self._invoice(1000)
        payment = self._pay(invoice)
        draft = self._invoice(200, post=False)
        cancelled = self._invoice(300, post=False)
        cancelled.button_cancel()
        self.assertEqual(cancelled.state, "cancel")
        Payment = type(self.env["account.payment"])
        with patch.object(Payment, "_get_email_invoice_candidates", lambda self: invoice | draft | cancelled):
            self.assertEqual(payment._get_email_invoices(), invoice)
            self.assertEqual(self._names(self._ours(self._composer(payment).attachment_ids)), self._file_names(invoice))

    def test_template_without_receipt_report(self):
        """Other templates of payments are not affected."""
        self._set_params(receipt=True)
        payment = self._pay(self._invoice(1000))
        template = self.template.copy({"report_template_ids": [Command.clear()]})
        composer = self._composer(payment, template=template)
        self.assertFalse(composer.attachment_ids)

    def test_multi_company(self):
        """Each payment uses the settings and excluded journals of its company."""
        company_2_data = self.setup_other_company()
        company_2 = company_2_data["company"]
        self.env.user.company_ids |= company_2
        self._set_params(receipt=True)
        self._set_params(company=company_2, journals=company_2_data["default_journal_sale"])

        invoice_1 = self._invoice(1000)
        payment_1 = self._pay(invoice_1)
        invoice_2 = self._invoice(1000, company=company_2)
        payment_2 = self.env["account.payment.register"].with_company(company_2).with_context(
            active_model="account.move", active_ids=invoice_2.ids
        ).create({"payment_date": "2026-01-02"})._create_payments()
        self.assertEqual(payment_2.company_id, company_2)

        self.assertEqual(self._names(self._ours(self._composer(payment_1).attachment_ids)), self._file_names(invoice_1))
        self.assertFalse(self._ours(self._composer(payment_2).attachment_ids), "Company 2 has the receipt setting off.")

        company_2.attach_invoices_on_receipt = True
        self.assertFalse(
            self._ours(self._composer(payment_2).attachment_ids), "Its sales journal is excluded in company 2."
        )
        company_2.no_attachment_journal_ids = False
        self.assertEqual(self._names(self._ours(self._composer(payment_2).attachment_ids)), self._file_names(invoice_2))
        # The excluded journals of company 2 have no effect on company 1.
        company_2.no_attachment_journal_ids = company_2_data["default_journal_sale"]
        self.assertEqual(self._names(self._ours(self._composer(payment_1).attachment_ids)), self._file_names(invoice_1))

    # ------------------------------------------------------------------
    # PDFs
    # ------------------------------------------------------------------

    def test_sale_pdf_is_the_stored_one(self):
        """The stored invoice PDF is reused as is; it is a valid PDF."""
        self._set_params(receipt=True)
        invoice = self._invoice(1000)
        stored = self.env["ir.attachment"].create(
            {
                "name": "stored.pdf",
                "raw": _pdf_bytes(2),
                "mimetype": "application/pdf",
                "res_model": "account.move",
                "res_id": invoice.id,
                "res_field": "invoice_pdf_report_file",
            }
        )
        invoice.invalidate_recordset(["invoice_pdf_report_id", "invoice_pdf_report_file"])
        self.assertEqual(invoice.invoice_pdf_report_id, stored)
        payment = self._pay(invoice)
        attached = self._ours(self._composer(payment).attachment_ids)
        self.assertEqual(attached.raw, stored.raw)
        self.assertNotEqual(attached, stored, "A temporary copy, never the stored attachment itself.")
        self.assertEqual(len(PdfReader(io.BytesIO(attached.raw)).pages), 2)

    def test_sale_pdf_rendered_without_storing(self):
        """Without a stored PDF, the document is rendered as the sending flow
        does it, and nothing is stored on the invoice."""
        self._set_params(receipt=True)
        invoice = self._invoice(1000)
        payment = self._pay(invoice)
        attachments_before = self.env["ir.attachment"].search_count(
            [("res_model", "=", "account.move"), ("res_id", "=", invoice.id)]
        )
        attached = self._ours(self._composer(payment).attachment_ids)

        report = self.env["account.move.send"]._get_default_pdf_report_id(invoice)
        invoice_data = {invoice: {"pdf_report": report}}
        self.env["account.move.send"]._prepare_invoice_pdf_report(invoice_data)
        self.assertEqual(attached.raw, invoice_data[invoice]["pdf_attachment_values"]["raw"])

        invoice.invalidate_recordset(["invoice_pdf_report_id", "invoice_pdf_report_file"])
        self.assertFalse(invoice.invoice_pdf_report_id)
        self.assertEqual(
            self.env["ir.attachment"].search_count([("res_model", "=", "account.move"), ("res_id", "=", invoice.id)]),
            attachments_before,
        )

    def test_vendor_bill_pdf(self):
        """Vendor bills: the PDF attached to the bill (main attachment, or any
        other PDF); a bill without a PDF is left out."""
        self._set_params(payment_order=True)
        with_main = self._bill(100, partner=self.partner_b)
        with_other_pdf = self._bill(200, partner=self.partner_b, with_pdf=False)
        other_pdf = self.env["ir.attachment"].create(
            {
                "name": "other.pdf",
                "raw": _pdf_bytes(3),
                "mimetype": "application/pdf",
                "res_model": "account.move",
                "res_id": with_other_pdf.id,
            }
        )
        with_other_pdf.message_main_attachment_id = self.env["ir.attachment"].create(
            {"name": "scan.png", "raw": b"\x89PNG\r\n\x1a\n", "res_model": "account.move", "res_id": with_other_pdf.id}
        )
        without_pdf = self._bill(300, partner=self.partner_b, with_pdf=False)
        payment = self._pay(with_main | with_other_pdf | without_pdf)

        attached = self._ours(self._composer(payment).attachment_ids)
        self.assertEqual(self._names(attached), self._file_names(with_main | with_other_pdf))
        by_name = {a.name: a for a in attached}
        self.assertEqual(by_name[with_main._get_payment_email_attachment_name()].raw, with_main.message_main_attachment_id.raw)
        self.assertEqual(by_name[with_other_pdf._get_payment_email_attachment_name()].raw, other_pdf.raw)
        for attachment in attached:
            self.assertTrue(PdfReader(io.BytesIO(attachment.raw)).pages)

    def test_file_names(self):
        """Invalid file name characters are replaced, and a name already taken
        in the email gets a suffix instead of overwriting it."""
        self._set_params(receipt=True)
        invoice = self._invoice(1000)
        self.assertNotIn("/", invoice._get_payment_email_attachment_name())
        self.assertTrue(invoice._get_payment_email_attachment_name().endswith(".pdf"))
        payment = self._pay(invoice)
        clashing = self.env["ir.attachment"].create(
            {"name": invoice._get_payment_email_attachment_name(), "raw": b"static", "res_model": "mail.template"}
        )
        template = self.template.copy({"attachment_ids": [Command.set(clashing.ids)]})
        composer = self._composer(payment, template=template)
        names = composer.attachment_ids.mapped("name")
        self.assertEqual(len(names), len(set(names)))
        stem = invoice._get_payment_email_attachment_name()[: -len(".pdf")]
        self.assertEqual(self._ours(composer.attachment_ids).name, f"{stem} (2).pdf")

    # ------------------------------------------------------------------
    # Original attachments, size, temporary attachments
    # ------------------------------------------------------------------

    def test_original_attachments_first_and_unchanged(self):
        """The receipt (and any attachment added by another module, like the
        withholding certificates) stays first and unchanged; the documents come
        last in the sent email."""
        invoice = self._invoice(1000)
        payment = self._pay(invoice)
        self._set_params()
        receipt_without = self._composer(payment).attachment_ids
        self._set_params(receipt=True)
        composer = self._composer(payment)
        receipt = composer.attachment_ids - self._ours(composer.attachment_ids)
        self.assertEqual(receipt.mapped("name"), receipt_without.mapped("name"))
        self.assertEqual(receipt.raw, receipt_without.raw)

        # Another module (e.g. l10n_ar_tax) appends its own attachment after
        # this module's preview: it gets a higher ID.
        certificate = self.env["ir.attachment"].create(
            {
                "name": "Certificados de Retención.pdf",
                "raw": _pdf_bytes(),
                "res_model": "mail.compose.message",
                "res_id": 0,
            }
        )
        composer.attachment_ids = [Command.link(certificate.id)]
        previews = self._ours(composer.attachment_ids)
        messages = composer._action_send_mail()[1]
        self.assertEqual(
            self._names(messages.attachment_ids),
            receipt.mapped("name") + ["Certificados de Retención.pdf"] + self._file_names(invoice),
        )
        self.assertFalse(previews.exists(), "The previous preview copies are deleted.")
        self.assertEqual(set(messages.attachment_ids.mapped("res_model")), {"account.payment"})

    def test_size_limit_warning(self):
        """Above the mail server limit, the composer warns with the total and
        the limit; no attachment is removed."""
        self._set_params(receipt=True)
        payment = self._pay(self._invoice(1000) | self._invoice(500))
        self.env["ir.mail_server"].sudo().search([]).write({"max_email_size": 0})
        self.env["ir.config_parameter"].sudo().set_param("base.default_max_email_size", "50")
        composer = self._composer(payment)
        self.assertFalse(composer.payment_attachment_size_warning)

        self.env["ir.config_parameter"].sudo().set_param("base.default_max_email_size", "0.001")
        composer = self._composer(payment)
        count = len(composer.attachment_ids)
        self.assertEqual(len(self._ours(composer.attachment_ids)), 2)
        composer.invalidate_recordset(["payment_attachment_size_warning"])
        warning = composer.payment_attachment_size_warning
        self.assertTrue(warning)
        self.assertIn(human_size(0.001 * 1024 * 1024), warning)
        self.assertEqual(len(composer.attachment_ids), count, "Nothing is removed.")
        messages = composer._action_send_mail()[1]
        self.assertEqual(len(messages.attachment_ids), count)

    def test_repeated_composer_no_extra_orphans(self):
        """Each opening adds one temporary copy per document, following the
        composer convention (garbage collected when never sent); the documents
        themselves get no new attachment."""
        self._set_params(receipt=True)
        invoice_1, invoice_2 = self._invoice(1000), self._invoice(500)
        payment = self._pay(invoice_1 | invoice_2)
        invoice_attachments = self.env["ir.attachment"].search_count(
            [("res_model", "=", "account.move"), ("res_id", "in", (invoice_1 | invoice_2).ids)]
        )
        composers = [self._composer(payment) for _index in range(3)]
        # Searched as superuser, like the garbage collector does: a user can't
        # search attachments not linked to a record.
        self.env.flush_all()
        temporary = self.env["ir.attachment"].sudo().search(
            [("description", "=", PAYMENT_INVOICE_MARKER), ("res_model", "=", "mail.compose.message"), ("res_id", "=", 0)]
        )
        self.assertEqual(len(temporary), 6)
        self.assertEqual(
            sorted(temporary.ids), sorted(self._ours(self.env["mail.compose.message"].concat(*composers).attachment_ids).ids)
        )

        sent = self._ours(composers[0]._action_send_mail()[1].attachment_ids)
        self.assertEqual(set(sent.mapped("res_model")), {"account.payment"})
        # The garbage collector removes the copies of the composers never sent.
        old = fields.Datetime.now() - timedelta(days=2)
        self.env.cr.execute(
            "UPDATE ir_attachment SET create_date = %s, write_date = %s WHERE id IN %s",
            (old, old, tuple((temporary | sent).ids)),
        )
        self.env["ir.attachment"].invalidate_model()
        self.env["mail.compose.message"].sudo()._gc_lost_attachments()
        self.assertEqual(sorted(temporary.exists().ids), sorted(sent.ids))
        self.assertEqual(
            self.env["ir.attachment"].search_count(
                [("res_model", "=", "account.move"), ("res_id", "in", (invoice_1 | invoice_2).ids)]
            ),
            invoice_attachments,
        )

    # ------------------------------------------------------------------
    # Sending flows without the composer form
    # ------------------------------------------------------------------

    def test_mass_mail(self):
        """Mass sending (list view action): each email carries its own documents."""
        self._set_params(receipt=True)
        invoice_1, invoice_2 = self._invoice(1000), self._invoice(500, partner=self.partner_b)
        payment_1, payment_2 = self._pay(invoice_1), self._pay(invoice_2)
        composer = self._composer(payment_1 | payment_2, mode="mass_mail")
        mails = composer._action_send_mail()[0]
        self.assertEqual(len(mails), 2)
        for payment, invoice in ((payment_1, invoice_1), (payment_2, invoice_2)):
            mail = mails.filtered(lambda m, p=payment: m.res_id == p.id)
            names = self._names(mail.attachment_ids)
            self.assertEqual(names[-1], invoice._get_payment_email_attachment_name())
            self.assertEqual(len(names), 2, "Receipt + its invoice only.")

    def test_message_post_with_source(self):
        """Automatic sending with a template (e.g. the receiptbook email on
        posting) goes through the same logic."""
        self._set_params(receipt=True)
        invoice = self._invoice(1000)
        payment = self._pay(invoice)
        message = payment.message_post_with_source(self.template, subtype_xmlid="mail.mt_comment")
        self.assertEqual(self._names(message.attachment_ids)[-1], invoice._get_payment_email_attachment_name())
        self.assertEqual(len(message.attachment_ids), 2)

    def test_scheduled_message(self):
        """A scheduled message keeps the documents."""
        self._set_params(receipt=True)
        invoice = self._invoice(1000)
        payment = self._pay(invoice)
        composer = self._composer(payment, scheduled_date=fields.Datetime.now() + timedelta(days=1))
        scheduled = composer._action_schedule_message()
        self.assertEqual(self._names(scheduled.attachment_ids)[-1], invoice._get_payment_email_attachment_name())

    # ------------------------------------------------------------------
    # Real composer form, non-admin user, exchange differences
    # ------------------------------------------------------------------

    def test_composer_form_remove_attachment(self):
        """Through the form (onchange on a new record, then save): the warning
        shows up, a removed document is not sent, the others still come last."""
        self._set_params(receipt=True)
        invoice_1, invoice_2 = self._invoice(1000), self._invoice(500)
        payment = self._pay(invoice_1 | invoice_2)
        self.env["ir.mail_server"].sudo().search([]).write({"max_email_size": 0})
        self.env["ir.config_parameter"].sudo().set_param("base.default_max_email_size", "0.001")
        form = Form(
            self.env["mail.compose.message"].with_context(
                default_model="account.payment",
                default_res_ids=payment.ids,
                default_composition_mode="comment",
                default_template_id=self.template.id,
            )
        )
        self.assertTrue(form.payment_attachment_size_warning)
        attachments = self.env["ir.attachment"].browse(form.attachment_ids.ids)
        removed = attachments.filtered(lambda a: a.name == invoice_1._get_payment_email_attachment_name())
        self.assertTrue(removed)
        form.attachment_ids.remove(id=removed.id)
        composer = form.save()
        # Attachment added after the preview, e.g. by the user.
        later = self.env["ir.attachment"].create(
            {"name": "later.pdf", "raw": _pdf_bytes(), "res_model": "mail.compose.message", "res_id": 0}
        )
        composer.attachment_ids = [Command.link(later.id)]
        names = self._names(composer._action_send_mail()[1].attachment_ids)
        self.assertNotIn(invoice_1._get_payment_email_attachment_name(), names)
        self.assertEqual(names[-2:], ["later.pdf", invoice_2._get_payment_email_attachment_name()])

    def test_non_admin_user(self):
        """The whole flow works for a plain invoicing user, preview copies
        moved last included."""
        self._set_params(receipt=True)
        invoice = self._invoice(1000)
        payment = self._pay(invoice)
        user = new_test_user(
            self.env,
            login="payment_email_billing",
            groups="base.group_user,account.group_account_invoice",
            company_id=self.company.id,
            lang="en_US",
        )
        composer = self.env["mail.compose.message"].with_user(user).with_context(
            default_model="account.payment",
            default_res_ids=payment.ids,
            default_composition_mode="comment",
            default_template_id=self.template.id,
        ).create({})
        self.assertEqual(self._names(self._ours(composer.attachment_ids)), self._file_names(invoice))
        later = self.env["ir.attachment"].with_user(user).create(
            {"name": "later.pdf", "raw": _pdf_bytes(), "res_model": "mail.compose.message", "res_id": 0}
        )
        composer.attachment_ids = [Command.link(later.id)]
        message = composer._action_send_mail()[1]
        self.assertEqual(self._names(message.sudo().attachment_ids)[-1], invoice._get_payment_email_attachment_name())

    def test_exchange_difference_not_attached(self):
        """A foreign currency invoice paid at another rate: only the invoice is
        attached, not the exchange difference entry."""
        self._set_params(receipt=True)
        currency = self.setup_other_currency("EUR", rates=[("2026-01-01", 2.0), ("2026-01-02", 4.0)])
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
                "date": "2026-01-01",
                "currency_id": currency.id,
                "invoice_line_ids": [Command.create({"name": "line", "quantity": 1, "price_unit": 100, "tax_ids": []})],
            }
        )
        invoice.action_post()
        payment = self._pay(invoice, currency_id=currency.id, amount=100)
        exchange_moves = (invoice.line_ids.matched_debit_ids | invoice.line_ids.matched_credit_ids).exchange_move_id
        self.assertTrue(exchange_moves, "Precondition: an exchange difference entry exists.")
        self.assertEqual(payment._get_email_invoices(), invoice)
        self.assertEqual(self._names(self._ours(self._composer(payment).attachment_ids)), self._file_names(invoice))
