from odoo.fields import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ar.tests.common import TestArCommon

# These tests exercise the purchase Concepto query directly
# (_vat_simple_build_purchase_query), so the moves used here don't need to be
# posted or carry a real ARCA document type/electronic journal - the query
# only looks at account_move_line rows by id, regardless of move state.


@tagged("post_install_l10n", "-at_install", "post_install")
class TestL10nArReportsSimpleImprovements(TestArCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lease_tag = cls.env.ref("l10n_ar_reports_simple.tag_leases_rentals_account")
        cls.fixed_asset_tag = cls.env.ref("l10n_ar_reports_simple.tag_fixed_asset_account")
        cls.goods_tag = cls.env.ref("l10n_ar_reports_simple_improvements.tag_goods_account")
        cls.services_tag = cls.env.ref("l10n_ar_reports_simple_improvements.tag_services_account")

        # A purchase VAT tax whose group's AFIP code is one of the codes the
        # query filters on ('3', '4', '5', '6', '8', '9')
        cls.vat_tax_group = cls.env["account.tax.group"].create({
            "name": "Test VAT Purchase Group",
            "l10n_ar_vat_afip_code": "5",
        })
        cls.vat_tax_purchase = cls.env["account.tax"].create({
            "name": "Test VAT Purchase 21%",
            "amount_type": "percent",
            "amount": 21,
            "type_tax_use": "purchase",
            "tax_group_id": cls.vat_tax_group.id,
        })

        expense_account = cls.company_data["default_account_expense"]
        cls.account_no_tag = expense_account.copy({"code": "9.9.01.001", "name": "No tag account", "tag_ids": [Command.clear()]})
        cls.account_lease = expense_account.copy({"code": "9.9.01.002", "name": "Lease account", "tag_ids": [Command.set(cls.lease_tag.ids)]})
        cls.account_fixed_asset = expense_account.copy({"code": "9.9.01.003", "name": "Fixed asset account", "tag_ids": [Command.set(cls.fixed_asset_tag.ids)]})
        cls.account_goods = expense_account.copy({"code": "9.9.01.004", "name": "Goods account", "tag_ids": [Command.set(cls.goods_tag.ids)]})
        cls.account_services = expense_account.copy({"code": "9.9.01.005", "name": "Services account", "tag_ids": [Command.set(cls.services_tag.ids)]})

        cls.product_consu = cls.env["product.product"].create({"name": "Test Good", "type": "consu"})
        cls.product_service = cls.env["product.product"].create({"name": "Test Service", "type": "service"})

    def _create_purchase_move(self, account, product=None, price_unit=1000.0):
        line_vals = {
            "price_unit": price_unit,
            "account_id": account.id,
            "tax_ids": [Command.set(self.vat_tax_purchase.ids)],
        }
        if product:
            line_vals["product_id"] = product.id
        else:
            line_vals["name"] = "Line without product"
        return self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.res_partner_adhoc.id,
            "invoice_date": "2026-01-01",
            "invoice_line_ids": [Command.create(line_vals)],
        })

    def _get_concept(self, move):
        handler = self.env["l10n_ar.tax.report.handler"]
        results = handler._vat_simple_build_purchase_query("purchase_invoice", tuple(move.ids))
        self.assertEqual(len(results), 1, "Expected a single aggregated Concepto/rate row for this move")
        return results[0]["Concepto"]

    def test_lease_tag_takes_priority(self):
        """Account tagged Locaciones -> Concepto 2, regardless of the product on the line."""
        move = self._create_purchase_move(self.account_lease, product=self.product_consu)
        self.assertEqual(self._get_concept(move), "2")

    def test_fixed_asset_tag_takes_priority(self):
        """Account tagged Bienes de Uso -> Concepto 4, regardless of the product on the line."""
        move = self._create_purchase_move(self.account_fixed_asset, product=self.product_service)
        self.assertEqual(self._get_concept(move), "4")

    def test_services_tag_without_product(self):
        """New tag: account tagged Servicios, no product on the line -> Concepto 3."""
        move = self._create_purchase_move(self.account_services)
        self.assertEqual(self._get_concept(move), "3")

    def test_goods_tag_without_product(self):
        """New tag: account tagged Bienes, no product on the line -> Concepto 1."""
        move = self._create_purchase_move(self.account_goods)
        self.assertEqual(self._get_concept(move), "1")

    def test_product_consu_without_tag(self):
        """Preexisting behavior must not break: product type 'consu', no account tag -> Concepto 1."""
        move = self._create_purchase_move(self.account_no_tag, product=self.product_consu)
        self.assertEqual(self._get_concept(move), "1")

    def test_product_service_without_tag(self):
        """Preexisting behavior must not break: product type 'service', no account tag -> Concepto 3."""
        move = self._create_purchase_move(self.account_no_tag, product=self.product_service)
        self.assertEqual(self._get_concept(move), "3")

    def test_no_product_no_tag_falls_back_to_services(self):
        """The bug fix: previously this fell back to Concepto 1 (Bien); now Concepto 3 (Servicio)."""
        move = self._create_purchase_move(self.account_no_tag)
        self.assertEqual(self._get_concept(move), "3")

    def test_constraint_blocks_more_than_one_concept_tag(self):
        """An account can't carry 2 of the 4 ARCA concept tags at the same time."""
        with self.assertRaises(ValidationError):
            self.account_no_tag.tag_ids = [Command.set((self.lease_tag | self.services_tag).ids)]

    def test_constraint_allows_a_single_concept_tag(self):
        """Sanity check: assigning just one concept tag is still allowed."""
        self.account_no_tag.tag_ids = [Command.set(self.goods_tag.ids)]
        self.assertEqual(self.account_no_tag.tag_ids, self.goods_tag)

    # Note: the optional "credit note vs invoice use separate files bucket" test described in
    # the module spec (documenting pre-existing, unmodified move_type-based bucket selection in
    # _vat_simple_get_csv_move_ids) was dropped here - it requires posting a fully valid AR
    # purchase invoice, which needs the vendor's own document number/type wired through AR's
    # l10n_latam onchange chain (compute+inverse fields), and doing that outside a Form-based UI
    # simulation proved unreliable in this environment. That behavior is untouched by this
    # module's changes and is already covered by upstream l10n_ar_reports_simple's own tests.
