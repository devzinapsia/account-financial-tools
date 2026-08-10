from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ar.tests.common import TestArCommon

# These tests only exercise local Odoo validation logic (view/model
# constraints). Posting invoices on electronic ("FEERCEL"/"RLI_RLM"-style)
# journals does not trigger any real ARCA/AFIP web service call in the
# community l10n_ar module (that integration lives in the Enterprise
# l10n_ar_edi module, not installed here), so no AFIP certificate or point
# of sale credentials are required to exercise every scenario below.


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

    def test_service_dates_required_raises_when_empty(self):
        """All conditions met, dates empty: creating the invoice raises ValidationError."""
        with self.assertRaisesRegex(ValidationError, "service billing period"):
            self._create_service_invoice(self.electronic_sale_journal)

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
        """Journal check disabled: dates are not required even if empty."""
        self.electronic_sale_journal.l10n_ar_service_period_dates_required = False
        invoice = self._create_service_invoice(self.electronic_sale_journal)
        self.assertFalse(invoice.l10n_ar_service_period_dates_required)

    def test_not_required_when_concept_is_products_only(self):
        """Concept is Products (not Services/Products and Services): dates not required even if empty."""
        invoice = self._create_invoice_ar(
            journal_id=self.electronic_sale_journal,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_iva_21)
            ],
        )
        self.assertEqual(invoice.l10n_ar_afip_concept, "1")
        self.assertFalse(invoice.l10n_ar_service_period_dates_required)

    def test_not_required_on_manual_preprinted_journal(self):
        """Pre-printed/manual journal (II_IM): dates not required even with
        the journal flag enabled, since the journal is not electronic."""
        manual_journal = self._create_journal(
            "preprinted", data={"l10n_ar_service_period_dates_required": True}
        )
        invoice = self._create_service_invoice(manual_journal)
        self.assertFalse(invoice.l10n_ar_service_period_dates_required)
