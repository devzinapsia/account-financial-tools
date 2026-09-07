import base64
from datetime import date
from pathlib import Path

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools.arca_xlsx_parser import parse_arca_file

DATA_DIR = Path(__file__).parent / "data"


@tagged("post_install", "-at_install")
class TestArcaBillComparison(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.company = cls.company_data["company"]
        cls.company.partner_id.vat = "30718972082"
        cls.ars = cls.env.ref("base.ARS")
        cls.ars.active = True

        cls.doc_type_a = cls.env.ref("l10n_ar.dc_a_f")  # code "1" - Factura A
        cls.doc_type_b = cls.env.ref("l10n_ar.dc_b_f")  # code "6" - Factura B
        cuit_type = cls.env.ref("l10n_ar.it_cuit")

        cls.journal_purchase = cls.env["account.journal"].create(
            {
                "name": "ARCA Test Purchase Journal",
                "type": "purchase",
                "code": "ARCAP",
                "company_id": cls.company.id,
                "l10n_latam_use_documents": True,
            }
        )

        cls.partner_amx = cls.env["res.partner"].create(
            {
                "name": "AMX ARGENTINA SOCIEDAD ANONIMA",
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "30663288497",
            }
        )
        cls.partner_allianz = cls.env["res.partner"].create(
            {
                "name": "ALLIANZ ARGENTINA COMPANIA DE SEGUROS S. A.",
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "30500037217",
            }
        )
        cls.partner_other = cls.env["res.partner"].create(
            {
                "name": "Other Test Vendor",
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "30111111118",
            }
        )

        cls.expense_account = cls.company_data["default_account_expense"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_rows(self, filename):
        return parse_arca_file((DATA_DIR / filename).read_bytes())

    def _create_bill(self, partner, doc_type, document_number, invoice_date, price_unit, tax=False):
        line_vals = {
            "name": "Test line",
            "quantity": 1,
            "price_unit": price_unit,
            "account_id": self.expense_account.id,
        }
        if tax:
            line_vals["tax_ids"] = [(6, 0, tax.ids)]
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": invoice_date,
                "currency_id": self.ars.id,
                "l10n_latam_document_type_id": doc_type.id,
                "l10n_latam_document_number": document_number,
                "invoice_line_ids": [(0, 0, line_vals)],
            }
        )

    def _create_wizard(self, filename, date_from=False, date_to=False):
        vals = {
            "file": base64.b64encode((DATA_DIR / filename).read_bytes()),
            "filename": filename,
        }
        if date_from:
            vals["date_from"] = date_from
        if date_to:
            vals["date_to"] = date_to
        return self.env["arca.bill.comparison.wizard"].with_company(self.company).create(vals)

    # ------------------------------------------------------------------
    # Parser-level tests
    # ------------------------------------------------------------------

    def test_voucher_type_code_extraction(self):
        rows = self._load_rows("mis_comprobantes_base.xlsx")
        self.assertEqual(rows[0]["voucher_type_raw"], "1 - Factura A")
        self.assertEqual(rows[0]["voucher_type_code"], "1")
        self.assertEqual(rows[1]["voucher_type_raw"], "6 - Factura B")
        self.assertEqual(rows[1]["voucher_type_code"], "6")

    def test_document_number_split(self):
        from ..tools.arca_xlsx_parser import split_document_number

        self.assertEqual(split_document_number("00005-00000303"), (5, 303))
        self.assertEqual(split_document_number("1340-373146"), (1340, 373146))
        self.assertEqual(split_document_number(False), (None, None))
        self.assertEqual(split_document_number("not-a-number"), (None, None))

    def test_empty_file(self):
        rows = self._load_rows("mis_comprobantes_vacio.xlsx")
        self.assertEqual(rows, [])

    # ------------------------------------------------------------------
    # Company VAT mismatch (section 5.1)
    # ------------------------------------------------------------------

    def test_company_vat_mismatch(self):
        wizard = self._create_wizard("mis_comprobantes_cuit_distinto.xlsx")
        try:
            wizard.action_process()
            self.fail("Expected a UserError for a company VAT mismatch.")
        except UserError as exc:
            message = str(exc)
            self.assertIn("no pertenece a la empresa actual", message)
            self.assertIn("30500000001", message)
            self.assertIn("30718972082", message)
        self.assertFalse(
            self.env["arca.bill.comparison.batch"].search([("company_id", "=", self.company.id)])
        )

    # ------------------------------------------------------------------
    # Range matching (section 9, file #2)
    # ------------------------------------------------------------------

    def test_range_matching(self):
        rows = self._load_rows("mis_comprobantes_rango.xlsx")
        range_row = next(
            row for row in rows if row["point_of_sale"] == 1340 and row["number_from"] == 7978664
        )
        self.assertEqual(range_row["number_to"], 7978666)

        move_lower = self._create_bill(
            self.partner_amx, self.doc_type_a, "1340-7978664", "2026-08-12", price_unit=100.0
        )
        move_middle = self._create_bill(
            self.partner_amx, self.doc_type_a, "1340-7978665", "2026-08-12", price_unit=100.0
        )
        move_upper = self._create_bill(
            self.partner_amx, self.doc_type_a, "1340-7978666", "2026-08-12", price_unit=100.0
        )
        move_outside = self._create_bill(
            self.partner_amx, self.doc_type_a, "1340-7978667", "2026-08-12", price_unit=100.0
        )

        wizard = self._create_wizard("mis_comprobantes_rango.xlsx", date_from="2026-08-01", date_to="2026-08-31")
        wizard.action_process()

        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        range_line = batch.line_ids.filtered(
            lambda line: line.arca_point_of_sale == "01340" and line.arca_number_from == "07978664"
        )
        self.assertEqual(len(range_line), 1)
        self.assertEqual(range_line.move_id, move_lower)

        pending_in_arca_move_ids = batch.line_ids.filtered(
            lambda line: line.result == "pending_in_arca"
        ).move_id.ids
        self.assertIn(move_outside.id, pending_in_arca_move_ids)
        for move in (move_lower, move_middle, move_upper):
            self.assertNotIn(move.id, pending_in_arca_move_ids)

    # ------------------------------------------------------------------
    # When a voucher carries no VAT on either side, ARCA sometimes reports
    # every breakdown column as zero even though the total is correct (real
    # case: exempt insurance premiums). Only the total should be compared
    # then, not the untaxed/tax split.
    # ------------------------------------------------------------------

    def test_no_vat_voucher_ignores_untaxed_breakdown_mismatch(self):
        rows = self._load_rows("mis_comprobantes_base.xlsx")
        no_vat_row = rows[1]  # Allianz: all breakdown columns 0, only Imp. Total set
        self.assertEqual(no_vat_row["total_vat"], 0.0)
        self.assertEqual(no_vat_row["other_taxes"], 0.0)

        move = self._create_bill(
            self.partner_allianz,
            self.doc_type_b,
            "%s-%s" % (no_vat_row["point_of_sale"], no_vat_row["number_from"]),
            no_vat_row["date"],
            price_unit=no_vat_row["total_amount"],
        )

        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard.action_process()

        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        line = batch.line_ids.filtered(lambda line: line.move_id == move)
        self.assertEqual(line.result, "match")
        self.assertFalse(line.difference_detail)

    # ------------------------------------------------------------------
    # A bill must never be linked from more than one result line, even if
    # two ARCA rows' ranges overlap (a data-quality issue on ARCA's side).
    # ------------------------------------------------------------------

    def _make_row(self, **overrides):
        row = {
            "date": None,
            "voucher_type_raw": "1 - Factura A",
            "voucher_type_code": "1",
            "point_of_sale": 1,
            "number_from": 1,
            "number_to": 1,
            "authorization_code": "1",
            "issuer_id_type": "CUIT",
            "issuer_vat": self.partner_amx.vat,
            "issuer_name": self.partner_amx.name,
            "recipient_id_type": "CUIT",
            "recipient_vat": self.company.partner_id.vat,
            "currency_raw": "$",
            "exchange_rate": 1.0,
        }
        for key in (
            "untaxed_vat_0", "vat_2_5", "untaxed_vat_2_5", "vat_5", "untaxed_vat_5",
            "vat_10_5", "untaxed_vat_10_5", "vat_21", "untaxed_vat_21", "vat_27",
            "untaxed_vat_27", "untaxed_total", "non_taxed_amount", "exempt_operations",
            "other_taxes", "total_vat", "total_amount",
        ):
            row[key] = 0.0
        row.update(overrides)
        return row

    def test_overlapping_ranges_do_not_duplicate_a_bill(self):
        move = self._create_bill(
            self.partner_amx, self.doc_type_a, "1-7", "2026-08-12", price_unit=100.0
        )
        rows = [
            self._make_row(date=date(2026, 8, 12), number_from=1, number_to=10, total_amount=100.0),
            self._make_row(date=date(2026, 8, 12), number_from=5, number_to=15, total_amount=100.0),
        ]
        batch = self.env["arca.bill.comparison.batch"].create(
            {"company_id": self.company.id, "date_from": "2026-08-01", "date_to": "2026-08-31"}
        )
        batch._run_comparison(rows)

        lines_with_move = batch.line_ids.filtered(lambda line: line.move_id == move)
        self.assertEqual(len(lines_with_move), 1)
        other_line = batch.line_ids - lines_with_move
        self.assertEqual(other_line.result, "pending_in_odoo")

    # ------------------------------------------------------------------
    # The four possible results (section 5.4), against the base file
    # ------------------------------------------------------------------

    def test_comparison_results(self):
        rows = self._load_rows("mis_comprobantes_base.xlsx")
        match_row = rows[0]
        difference_row = rows[1]

        fixed_tax = self.env["account.tax"].create(
            {
                "name": "ARCA test fixed tax",
                "amount_type": "fixed",
                "amount": match_row["total_vat"] + match_row["other_taxes"],
                "type_tax_use": "purchase",
                "company_id": self.company.id,
            }
        )
        match_move = self._create_bill(
            self.partner_amx,
            self.doc_type_a,
            "%s-%s" % (match_row["point_of_sale"], match_row["number_from"]),
            match_row["date"],
            price_unit=match_row["untaxed_total"] + match_row["non_taxed_amount"] + match_row["exempt_operations"],
            tax=fixed_tax,
        )

        # Total amount itself doesn't match ARCA's, which is always compared
        # regardless of whether the voucher carries any VAT.
        difference_move = self._create_bill(
            self.partner_allianz,
            self.doc_type_b,
            "%s-%s" % (difference_row["point_of_sale"], difference_row["number_from"]),
            difference_row["date"],
            price_unit=difference_row["total_amount"] - 50.0,
        )

        pending_in_arca_move = self._create_bill(
            self.partner_other, self.doc_type_a, "9999-1", "2026-08-15", price_unit=500.0
        )

        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard.action_process()

        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        self.assertEqual(batch.line_count, len(rows) + 1)

        match_line = batch.line_ids.filtered(lambda line: line.move_id == match_move)
        self.assertEqual(match_line.result, "match")
        self.assertFalse(match_line.difference_detail)

        difference_line = batch.line_ids.filtered(lambda line: line.move_id == difference_move)
        self.assertEqual(difference_line.result, "difference")
        self.assertIn("Total amount", difference_line.difference_detail)

        pending_in_arca_line = batch.line_ids.filtered(lambda line: line.move_id == pending_in_arca_move)
        self.assertEqual(pending_in_arca_line.result, "pending_in_arca")

        pending_in_odoo_lines = batch.line_ids.filtered(lambda line: line.result == "pending_in_odoo")
        self.assertEqual(len(pending_in_odoo_lines), len(rows) - 2)
