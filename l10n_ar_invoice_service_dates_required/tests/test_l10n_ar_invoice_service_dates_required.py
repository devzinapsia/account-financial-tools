from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from odoo.addons.l10n_ar.tests.common import TestArCommon

# These tests only exercise local Odoo validation logic (model constraints
# and the _post() override). Posting invoices on electronic
# ("FEERCEL"/"RLI_RLM"-style) journals does not trigger any real ARCA/AFIP
# web service call in the community l10n_ar module (that integration lives
# in the Enterprise l10n_ar_edi module, not installed here), so no AFIP
# certificate or point of sale credentials are required to exercise every
# scenario below.


@tagged("post_install_l10n", "-at_install", "post_install")
class TestL10nArInvoiceServiceDatesRequired(TestArCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.res_partner_adhoc

        cls.electronic_sale_journal = cls.env["account.journal"].create(
            {
                "name": "Electronic Sales Journal (Service Dates Required)",
                "company_id": cls.company_ri.id,
                "type": "sale",
                "code": "S0099",
                "l10n_latam_use_documents": True,
                "l10n_ar_afip_pos_number": 99,
                "l10n_ar_afip_pos_partner_id": cls.partner_ri.id,
                "l10n_ar_afip_pos_system": "RLI_RLM",
                "l10n_ar_service_period_dates_required": True,
                "refund_sequence": False,
            }
        )

    def _create_service_invoice(self, journal, **kwargs):
        vals = {
            "journal_id": journal,
            "invoice_line_ids": [
                self._prepare_invoice_line(product_id=self.service_iva_21)
            ],
        }
        vals.update(kwargs)
        return self._create_invoice_ar(**vals)

    def test_journal_field_default_false(self):
        """A newly created sales journal has the validation flag off by default."""
        journal = self.env["account.journal"].create(
            {
                "name": "Plain Sales Journal",
                "company_id": self.company_ri.id,
                "type": "sale",
                "code": "S0098",
            }
        )
        self.assertFalse(journal.l10n_ar_service_period_dates_required)

    def test_draft_save_allowed_with_empty_dates(self):
        """All conditions met, dates empty: the invoice can still be created
        and kept as a draft without raising, since the check only applies
        when confirming."""
        invoice = self._create_service_invoice(self.electronic_sale_journal)
        self.assertEqual(invoice.state, "draft")
        self.assertTrue(invoice.l10n_ar_service_period_dates_required)
        self.assertFalse(invoice.l10n_ar_afip_service_start)
        self.assertFalse(invoice.l10n_ar_afip_service_end)

    def test_post_raises_when_dates_empty(self):
        """All conditions met, dates empty: confirming (posting) the
        invoice raises ValidationError. Forces English so the assertion is
        independent of the database's default language."""
        invoice = self._create_service_invoice(self.electronic_sale_journal)
        with self.assertRaisesRegex(ValidationError, "service billing period"):
            invoice.with_context(lang="en_US").action_post()
        self.assertEqual(invoice.state, "draft")

    def test_post_error_message_is_translated_to_spanish(self):
        """The validation error raised on post must be translated when the
        user's language is Spanish (regression test: code-based
        translations require the "#. odoo-python" comment marker in the .po
        file next to the "#: code:addons/..." reference, otherwise Odoo
        silently ignores the translation and always shows the English
        source string)."""
        self.env["res.lang"]._activate_lang("es_AR")
        invoice = self._create_service_invoice(self.electronic_sale_journal)
        with self.assertRaises(ValidationError) as capture:
            invoice.with_context(lang="es_AR").action_post()
        self.assertIn("OTRA INFORMACIÓN", str(capture.exception))

    def test_service_dates_required_saves_when_filled(self):
        """All conditions met, dates filled in: the invoice saves and posts without error."""
        invoice = self._create_service_invoice(
            self.electronic_sale_journal,
            l10n_ar_afip_service_start="2026-01-01",
            l10n_ar_afip_service_end="2026-01-31",
        )
        self.assertTrue(invoice.l10n_ar_service_period_dates_required)
        self._post(invoice)
        self.assertEqual(invoice.state, "posted")

    def test_not_required_when_journal_flag_disabled(self):
        """Journal check disabled: dates are not required, even to post."""
        self.electronic_sale_journal.l10n_ar_service_period_dates_required = False
        invoice = self._create_service_invoice(self.electronic_sale_journal)
        self.assertFalse(invoice.l10n_ar_service_period_dates_required)
        self._post(invoice)
        self.assertEqual(invoice.state, "posted")

    def test_not_required_when_concept_is_products_only(self):
        """Concept is Products (not Services/Products and Services): dates
        are not required, even to post."""
        invoice = self._create_invoice_ar(
            journal_id=self.electronic_sale_journal,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_iva_21)
            ],
        )
        self.assertEqual(invoice.l10n_ar_afip_concept, "1")
        self.assertFalse(invoice.l10n_ar_service_period_dates_required)
        self._post(invoice)
        self.assertEqual(invoice.state, "posted")

    def test_not_required_on_manual_preprinted_journal(self):
        """Pre-printed/manual journal (II_IM): dates not required even with
        the journal flag enabled, since the journal is not electronic."""
        manual_journal = self._create_journal(
            "preprinted", data={"l10n_ar_service_period_dates_required": True}
        )
        invoice = self._create_service_invoice(manual_journal)
        self.assertFalse(invoice.l10n_ar_service_period_dates_required)
        self._post(invoice)
        self.assertEqual(invoice.state, "posted")

    def test_journal_new_options_defaults(self):
        """A new sales journal proposes the invoice month and prints the
        invoiced period by default."""
        journal = self.env["account.journal"].create(
            {
                "name": "Plain Sales Journal",
                "company_id": self.company_ri.id,
                "type": "sale",
                "code": "S0097",
            }
        )
        self.assertEqual(journal.l10n_ar_service_period_default, "invoice_month")
        self.assertTrue(journal.l10n_ar_service_period_print)

    def _create_dated_service_invoice(self, mode):
        self.electronic_sale_journal.write(
            {
                "l10n_ar_service_period_dates_required": False,
                "l10n_ar_service_period_default": mode,
            }
        )
        return self._create_service_invoice(
            self.electronic_sale_journal, invoice_date="2026-10-15"
        )

    def test_default_period_invoice_month_proposed(self):
        """Invoice month option: the form proposes the whole invoice month."""
        invoice = self._create_dated_service_invoice("invoice_month")
        invoice._onchange_l10n_ar_default_service_period()
        self.assertEqual(
            invoice.l10n_ar_afip_service_start, fields.Date.to_date("2026-10-01")
        )
        self.assertEqual(
            invoice.l10n_ar_afip_service_end, fields.Date.to_date("2026-10-31")
        )

    def test_default_period_invoice_day_proposed(self):
        """Invoice day option: the form proposes the invoice date as both
        start and end."""
        invoice = self._create_dated_service_invoice("invoice_day")
        invoice._onchange_l10n_ar_default_service_period()
        self.assertEqual(invoice.l10n_ar_afip_service_start, invoice.invoice_date)
        self.assertEqual(invoice.l10n_ar_afip_service_end, invoice.invoice_date)

    def test_default_period_empty_not_proposed(self):
        """Empty option: nothing is proposed in the form."""
        invoice = self._create_dated_service_invoice("empty")
        invoice._onchange_l10n_ar_default_service_period()
        self.assertFalse(invoice.l10n_ar_afip_service_start)
        self.assertFalse(invoice.l10n_ar_afip_service_end)

    def test_default_period_does_not_overwrite_user_dates(self):
        """Dates already entered by the user are kept."""
        invoice = self._create_dated_service_invoice("invoice_day")
        invoice.write(
            {
                "l10n_ar_afip_service_start": "2026-09-01",
                "l10n_ar_afip_service_end": "2026-09-30",
            }
        )
        invoice._onchange_l10n_ar_default_service_period()
        self.assertEqual(
            invoice.l10n_ar_afip_service_start, fields.Date.to_date("2026-09-01")
        )
        self.assertEqual(
            invoice.l10n_ar_afip_service_end, fields.Date.to_date("2026-09-30")
        )

    def test_default_period_not_proposed_for_products_concept(self):
        """Products concept: the journal default period does not apply."""
        self.electronic_sale_journal.l10n_ar_service_period_default = "invoice_day"
        invoice = self._create_invoice_ar(
            journal_id=self.electronic_sale_journal,
            invoice_date="2026-10-15",
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_iva_21)
            ],
        )
        invoice._onchange_l10n_ar_default_service_period()
        self.assertFalse(invoice.l10n_ar_afip_service_start)

    def test_post_fills_empty_dates_with_invoice_day(self):
        """Invoice day option, dates not required and left empty: posting
        fills them with the invoice date instead of the invoice month."""
        invoice = self._create_dated_service_invoice("invoice_day")
        self._post(invoice)
        self.assertEqual(invoice.l10n_ar_afip_service_start, invoice.invoice_date)
        self.assertEqual(invoice.l10n_ar_afip_service_end, invoice.invoice_date)

    def test_post_fills_empty_dates_with_invoice_month(self):
        """Invoice month option, dates left empty: posting keeps the
        standard l10n_ar invoice month fallback."""
        invoice = self._create_dated_service_invoice("invoice_month")
        self._post(invoice)
        self.assertEqual(
            invoice.l10n_ar_afip_service_start, fields.Date.to_date("2026-10-01")
        )
        self.assertEqual(
            invoice.l10n_ar_afip_service_end, fields.Date.to_date("2026-10-31")
        )

    def _render_invoice_html(self, invoice):
        # The report renders in the partner's language: pin it to English so
        # the assertions don't depend on the loaded languages.
        invoice.partner_id.lang = "en_US"
        html, _format = (
            self.env["ir.actions.report"]
            .with_context(lang="en_US")
            ._render_qweb_html("account.account_invoices", invoice.ids)
        )
        return html.decode() if isinstance(html, bytes) else html

    def test_print_invoiced_period_by_default(self):
        """Print option enabled (default): the invoiced period is printed."""
        invoice = self._create_service_invoice(
            self.electronic_sale_journal,
            l10n_ar_afip_service_start="2026-09-01",
            l10n_ar_afip_service_end="2026-09-30",
        )
        self._post(invoice)
        self.assertTrue(invoice._l10n_ar_print_service_period())
        self.assertIn("Invoiced period", self._render_invoice_html(invoice))

    def test_no_print_invoiced_period_when_disabled(self):
        """Print option disabled: the invoiced period is not printed."""
        self.electronic_sale_journal.l10n_ar_service_period_print = False
        invoice = self._create_service_invoice(
            self.electronic_sale_journal,
            l10n_ar_afip_service_start="2026-09-01",
            l10n_ar_afip_service_end="2026-09-30",
        )
        self._post(invoice)
        self.assertFalse(invoice._l10n_ar_print_service_period())
        self.assertNotIn("Invoiced period", self._render_invoice_html(invoice))

    def test_print_option_ignored_on_manual_preprinted_journal(self):
        """Pre-printed/manual journal (II_IM): the print option does not
        apply, since the journal is not electronic."""
        manual_journal = self._create_journal(
            "preprinted", data={"l10n_ar_service_period_print": False}
        )
        invoice = self._create_service_invoice(manual_journal)
        self.assertTrue(invoice._l10n_ar_print_service_period())

    # --- Duplicated invoices -------------------------------------------------

    def _posted_service_invoice(self):
        """Posted service invoice dated 2026-10-01 for the previous month's
        service (September), as billed in arrears."""
        invoice = self._create_service_invoice(
            self.electronic_sale_journal,
            invoice_date="2026-10-01",
            l10n_ar_afip_service_start="2026-09-01",
            l10n_ar_afip_service_end="2026-09-30",
        )
        self._post(invoice)
        return invoice

    def _assert_period(self, move, start, end):
        self.assertEqual(move.l10n_ar_afip_service_start, fields.Date.to_date(start))
        self.assertEqual(move.l10n_ar_afip_service_end, fields.Date.to_date(end))

    def test_duplicate_clears_period(self):
        """Duplicating an electronic service invoice does not carry over
        the original's service period, and marks the copy so the journal
        default is not proposed."""
        duplicate = self._posted_service_invoice().copy()
        self.assertFalse(duplicate.l10n_ar_afip_service_start)
        self.assertFalse(duplicate.l10n_ar_afip_service_end)
        self.assertTrue(duplicate.l10n_ar_service_period_no_default)

    def test_duplicate_period_not_proposed_and_required_at_post(self):
        """Invoice month default and required dates: setting the invoice
        date on a duplicate does not propose the period, so confirming it
        raises until the user enters the period."""
        duplicate = self._posted_service_invoice().copy()
        with Form(duplicate) as form:
            form.invoice_date = fields.Date.to_date("2026-11-01")
        self.assertFalse(duplicate.l10n_ar_afip_service_start)
        self.assertFalse(duplicate.l10n_ar_afip_service_end)
        with self.assertRaisesRegex(ValidationError, "service billing period"):
            duplicate.with_context(lang="en_US").action_post()

        with Form(duplicate) as form:
            form.l10n_ar_afip_service_start = fields.Date.to_date("2026-10-01")
            form.l10n_ar_afip_service_end = fields.Date.to_date("2026-10-31")
        self._post(duplicate)
        self._assert_period(duplicate, "2026-10-01", "2026-10-31")

    def test_duplicate_not_required_filled_at_post(self):
        """Dates not required: a duplicate left without period is still
        filled in at posting with the invoice month, as before."""
        original = self._posted_service_invoice()
        self.electronic_sale_journal.l10n_ar_service_period_dates_required = False
        duplicate = original.copy()
        with Form(duplicate) as form:
            form.invoice_date = fields.Date.to_date("2026-11-01")
        self.assertFalse(duplicate.l10n_ar_afip_service_start)
        self._post(duplicate)
        self._assert_period(duplicate, "2026-11-01", "2026-11-30")

    def test_duplicate_products_concept_untouched(self):
        """Products concept: the duplicate is out of this module's scope and
        is not marked."""
        invoice = self._create_invoice_ar(
            journal_id=self.electronic_sale_journal,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_iva_21)
            ],
        )
        self.assertFalse(invoice.copy().l10n_ar_service_period_no_default)

    def test_credit_note_keeps_period(self):
        """Credit notes keep the original's service period (l10n_ar
        standard) and are not marked as duplicates."""
        invoice = self._posted_service_invoice()
        wizard = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "test", "journal_id": invoice.journal_id.id})
        )
        wizard.refund_moves()
        credit_note = invoice.reversal_move_ids
        self._assert_period(credit_note, "2026-09-01", "2026-09-30")
        self.assertFalse(credit_note.l10n_ar_service_period_no_default)

    def test_reverse_and_create_invoice_not_marked(self):
        """The corrected invoice created by "Reverse and create invoice" is
        not a plain duplicate: it is not marked and keeps the standard
        l10n_ar behavior (the original's period is copied)."""
        invoice = self._posted_service_invoice()
        wizard = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "test", "journal_id": invoice.journal_id.id})
        )
        wizard.modify_moves()
        new_invoice = self.env["account.move"].search(
            [
                ("journal_id", "=", invoice.journal_id.id),
                ("move_type", "=", "out_invoice"),
                ("id", ">", invoice.reversal_move_ids.id),
            ]
        )
        self.assertEqual(len(new_invoice), 1)
        self.assertFalse(new_invoice.l10n_ar_service_period_no_default)
        self._assert_period(new_invoice, "2026-09-01", "2026-09-30")

    def test_debit_note_not_marked(self):
        """Debit notes are not plain duplicates: they are not marked."""
        invoice = self._posted_service_invoice()
        wizard = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "test", "copy_lines": True})
        )
        wizard.create_debit()
        self.assertTrue(invoice.debit_note_ids)
        self.assertFalse(invoice.debit_note_ids.l10n_ar_service_period_no_default)

    # --- Proposed period follows the invoice date ----------------------------

    def _new_invoice_form(self):
        form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        form.partner_id = self.partner
        form.journal_id = self.electronic_sale_journal
        with form.invoice_line_ids.new() as line:
            line.product_id = self.service_iva_21
        return form

    def test_proposed_period_follows_invoice_date(self):
        """A proposed period follows the invoice date when it is changed
        before saving (e.g. today's date first, then corrected)."""
        form = self._new_invoice_form()
        form.invoice_date = fields.Date.to_date("2026-10-27")
        self.assertEqual(
            form.l10n_ar_afip_service_start, fields.Date.to_date("2026-10-01")
        )
        form.invoice_date = fields.Date.to_date("2026-11-01")
        invoice = form.save()
        self._assert_period(invoice, "2026-11-01", "2026-11-30")
        self.assertTrue(invoice.l10n_ar_service_period_proposed)

    def test_proposed_period_follows_invoice_date_after_save(self):
        """A proposed period saved on the draft still follows a later
        change of the invoice date."""
        form = self._new_invoice_form()
        form.invoice_date = fields.Date.to_date("2026-10-27")
        invoice = form.save()
        self._assert_period(invoice, "2026-10-01", "2026-10-31")
        with Form(invoice) as form:
            form.invoice_date = fields.Date.to_date("2026-11-01")
        self._assert_period(invoice, "2026-11-01", "2026-11-30")

    def test_user_changed_period_not_following_invoice_date(self):
        """Once the user changes a proposed period, a later change of the
        invoice date keeps the user's period."""
        form = self._new_invoice_form()
        form.invoice_date = fields.Date.to_date("2026-10-27")
        form.l10n_ar_afip_service_start = fields.Date.to_date("2026-09-01")
        form.l10n_ar_afip_service_end = fields.Date.to_date("2026-09-30")
        form.invoice_date = fields.Date.to_date("2026-11-01")
        invoice = form.save()
        self._assert_period(invoice, "2026-09-01", "2026-09-30")
        self.assertFalse(invoice.l10n_ar_service_period_proposed)
