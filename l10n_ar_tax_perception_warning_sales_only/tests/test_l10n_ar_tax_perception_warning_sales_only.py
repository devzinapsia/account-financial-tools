from lxml import etree

from odoo.tests import TransactionCase, tagged

SALE_TYPES = ("out_invoice", "out_refund", "out_receipt")


@tagged("post_install", "-at_install")
class TestL10nArTaxPerceptionWarningSalesOnly(TransactionCase):

    def _get_banner(self):
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        banners = [
            div
            for div in etree.fromstring(arch).iter("div")
            if "alert-warning" in (div.get("class") or "").split()
            and div.find(".//field[@name='fiscal_position_id']") is not None
        ]
        self.assertEqual(len(banners), 1, "The l10n_ar_tax perception banner must be found exactly once")
        return banners[0]

    def test_banner_restricted_to_sale_documents(self):
        """The banner is hidden on every non-sale move type."""
        invisible = self._get_banner().get("invisible")
        self.assertIn("move_type not in", invisible)
        for move_type in SALE_TYPES:
            self.assertIn(move_type, invisible)
        for move_type in ("in_invoice", "in_refund", "in_receipt", "entry"):
            self.assertNotIn(f"'{move_type}'", invisible)

    def test_original_conditions_kept(self):
        """The l10n_ar_tax conditions (no invoice date, perceptions FP) still apply."""
        invisible = self._get_banner().get("invisible")
        self.assertIn("invoice_date", invisible)
        self.assertIn("not perceptions_fiscal_positon", invisible)

    def test_move_type_available_in_form(self):
        """move_type is loaded in the form, so the condition can be evaluated client side."""
        arch = etree.fromstring(self.env["account.move"].get_view(view_type="form")["arch"])
        self.assertTrue(arch.xpath("//field[@name='move_type']"))
