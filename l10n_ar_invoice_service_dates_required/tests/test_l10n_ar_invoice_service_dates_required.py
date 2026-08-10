from odoo.exceptions import ValidationError
from odoo.tests import tagged

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
