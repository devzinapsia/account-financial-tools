import base64
from datetime import date
from pathlib import Path

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools.arca_file_parser import parse_arca_file

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
        return parse_arca_file((DATA_DIR / filename).read_bytes(), filename)

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
        from ..tools.arca_file_parser import split_document_number

        self.assertEqual(split_document_number("00005-00000303"), (5, 303))
        self.assertEqual(split_document_number("1340-373146"), (1340, 373146))
        self.assertEqual(split_document_number(False), (None, None))
        self.assertEqual(split_document_number("not-a-number"), (None, None))

    def test_resolve_currency_code(self):
        from ..tools.arca_file_parser import resolve_currency_code

        self.assertEqual(resolve_currency_code("$"), "ARS")
        self.assertEqual(resolve_currency_code("u$s"), "USD")
        # Real case: ARCA sends the literal code "USD" for some vouchers
        # instead of its usual "u$s" symbol.
        self.assertEqual(resolve_currency_code("USD"), "USD")
        self.assertEqual(resolve_currency_code("EUR"), "EUR")
        self.assertEqual(resolve_currency_code("€"), "EUR")
        self.assertIsNone(resolve_currency_code("XYZ"))

    def test_empty_file(self):
        rows = self._load_rows("mis_comprobantes_vacio.xlsx")
        self.assertEqual(rows, [])

    def test_csv_parsing_basic(self):
        rows = self._load_rows("mis_comprobantes_base.csv")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], date(2026, 8, 1))
        self.assertEqual(rows[0]["point_of_sale"], 1340)
        self.assertEqual(rows[0]["total_amount"], 120271.80)
        # Unlike the xlsx export, the csv export only gives the bare AFIP
        # code, not "<code> - <name>" text.
        self.assertEqual(rows[0]["voucher_type_code"], "1")
        self.assertEqual(rows[0]["voucher_type_raw"], "1")
        # AFIP's numeric "Tipo de Documento" code (80) must resolve to the
        # same "CUIT" text the xlsx export already gives.
        self.assertEqual(rows[0]["issuer_id_type"], "CUIT")

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
            self.assertTrue(message.rstrip().endswith(")"))
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
    # A voucher type mismatch (same issuer/point of sale/number, different
    # type) must be linked as a Difference, not shown as two disconnected
    # Pending lines. Real case: ARCA reports "81 - Tique Factura A" for a
    # bill entered in Odoo as "1 - Factura A".
    # ------------------------------------------------------------------

    def test_voucher_type_mismatch_links_as_difference(self):
        move = self._create_bill(
            self.partner_amx, self.doc_type_a, "35-2321", "2026-08-23", price_unit=8400.0
        )
        rows = [
            self._make_row(
                date=date(2026, 8, 23),
                voucher_type_raw="81 - Tique Factura A",
                voucher_type_code="81",
                point_of_sale=35,
                number_from=2321,
                number_to=2321,
                total_amount=8400.0,
            ),
        ]
        batch = self.env["arca.bill.comparison.batch"].create(
            {"company_id": self.company.id, "date_from": "2026-08-01", "date_to": "2026-08-31"}
        )
        batch._run_comparison(rows)

        self.assertEqual(len(batch.line_ids), 1)
        line = batch.line_ids
        self.assertEqual(line.move_id, move)
        self.assertEqual(line.result, "difference")
        self.assertIn("Voucher type", line.difference_detail)

    def test_issuer_vat_mismatch_links_as_difference_when_amount_agrees(self):
        """Real case: a bill booked against a related but wrong vendor (e.g.
        a "Telecom Personal S.A." invoice booked as "Telecom Argentina
        S.A." in Odoo). Point of sale/number/total amount all agree, so it
        should link as a Difference noting the issuer mismatch instead of
        showing up as two disconnected Pending lines."""
        move = self._create_bill(
            self.partner_amx, self.doc_type_a, "35-2321", "2026-08-23", price_unit=8400.0
        )
        rows = [
            self._make_row(
                date=date(2026, 8, 23),
                point_of_sale=35,
                number_from=2321,
                number_to=2321,
                issuer_vat=self.partner_allianz.vat,
                issuer_name=self.partner_allianz.name,
                total_amount=8400.0,
            ),
        ]
        batch = self.env["arca.bill.comparison.batch"].create(
            {"company_id": self.company.id, "date_from": "2026-08-01", "date_to": "2026-08-31"}
        )
        batch._run_comparison(rows)

        self.assertEqual(len(batch.line_ids), 1)
        line = batch.line_ids
        self.assertEqual(line.move_id, move)
        self.assertEqual(line.result, "difference")
        self.assertIn("Issuer", line.difference_detail)

    def test_issuer_vat_mismatch_stays_pending_when_amount_disagrees(self):
        """Without amount agreement too, a point of sale/number coincidence
        across two different vendors must never be linked — that combination
        alone is too weak a signal on its own."""
        move = self._create_bill(
            self.partner_amx, self.doc_type_a, "35-2321", "2026-08-23", price_unit=8400.0
        )
        rows = [
            self._make_row(
                date=date(2026, 8, 23),
                point_of_sale=35,
                number_from=2321,
                number_to=2321,
                issuer_vat=self.partner_allianz.vat,
                issuer_name=self.partner_allianz.name,
                total_amount=999.0,
            ),
        ]
        batch = self.env["arca.bill.comparison.batch"].create(
            {"company_id": self.company.id, "date_from": "2026-08-01", "date_to": "2026-08-31"}
        )
        batch._run_comparison(rows)

        results = {line.result for line in batch.line_ids}
        self.assertEqual(results, {"pending_in_odoo", "pending_in_arca"})
        # The move is referenced from its own "Pending in ARCA" line (by
        # design), but never from a "match"/"difference" line.
        matched_or_different = batch.line_ids.filtered(lambda line: line.result in ("match", "difference"))
        self.assertNotIn(move, matched_or_different.mapped("move_id"))

    # ------------------------------------------------------------------
    # Document types with no point of sale component (e.g. foreign-invoice
    # documents, where the accountant types a free-form number) must still
    # show the full document number instead of a blank column.
    # ------------------------------------------------------------------

    def test_move_without_point_of_sale_shows_full_document_number(self):
        doc_type_exterior = self.env.ref("l10n_ar.fa_exterior")
        move = self._create_bill(
            self.partner_amx, doc_type_exterior, "INV-2024-00123", "2026-08-12", price_unit=100.0
        )
        batch = self.env["arca.bill.comparison.batch"].create(
            {"company_id": self.company.id, "date_from": "2026-08-01", "date_to": "2026-08-31"}
        )
        batch._run_comparison([])

        line = batch.line_ids.filtered(lambda line: line.move_id == move)
        self.assertEqual(line.result, "pending_in_arca")
        self.assertEqual(line.arca_point_of_sale, "")
        self.assertEqual(line.arca_number_from, "INV-2024-00123")
        self.assertEqual(line.arca_number_to, "INV-2024-00123")

    # ------------------------------------------------------------------
    # csv import: same comparison engine, different source file format.
    # ------------------------------------------------------------------

    def test_csv_import_links_and_enriches_voucher_type(self):
        rows = self._load_rows("mis_comprobantes_base.csv")
        match_row = rows[0]
        move = self._create_bill(
            self.partner_amx,
            self.doc_type_a,
            "%s-%s" % (match_row["point_of_sale"], match_row["number_from"]),
            match_row["date"],
            price_unit=match_row["untaxed_total"] + match_row["non_taxed_amount"] + match_row["exempt_operations"],
        )
        wizard = self._create_wizard("mis_comprobantes_base.csv")
        wizard.action_process()

        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        line = batch.line_ids.filtered(lambda line: line.move_id == move)
        self.assertTrue(line)
        # The csv only gives the bare code ("1"); the grid should show it
        # the same way the xlsx export's own text does.
        self.assertEqual(line.arca_voucher_type_raw, "1 - Factura A")

    # ------------------------------------------------------------------
    # Storing the source file in Documents, and reprocessing it later.
    # ------------------------------------------------------------------

    def test_process_stores_source_file_in_documents(self):
        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard.action_process()

        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        self.assertTrue(batch.source_document_id)
        # Prefixed with the run's own date range, since ARCA always names
        # this export the same way.
        self.assertEqual(
            batch.source_document_id.name,
            "%s - %s - mis_comprobantes_base.xlsx" % (batch.date_from, batch.date_to),
        )
        self.assertEqual(batch.source_document_id.folder_id.name, "Mis comprobantes ARCA")
        self.assertEqual(batch.source_document_id.folder_id.folder_id.name, "Zinapsia")
        self.assertTrue(batch.last_processed_on)

    def test_action_process_result_clears_breadcrumb(self):
        # Otherwise this inherits whatever page was open behind the
        # wizard's modal dialog instead of starting clean.
        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        action = wizard.action_process()
        self.assertEqual(action.get("target"), "main")

    def test_action_view_lines_keeps_breadcrumb(self):
        # Reached from a run's own "Results"/"Reprocess" button, this must
        # NOT clear the breadcrumb, or there's no way back to that run.
        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard.action_process()
        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        action = batch.action_view_lines()
        self.assertNotEqual(action.get("target"), "main")

    def test_delete_run_archives_source_document(self):
        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard.action_process()
        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        document = batch.source_document_id
        self.assertTrue(document.active)

        batch.unlink()

        # Archived (sent to the Documents trash), not hard-deleted, same as
        # manually deleting it from Documents.
        self.assertFalse(document.active)

    def test_get_or_create_arca_documents_folder_is_idempotent(self):
        batch = self.env["arca.bill.comparison.batch"].create(
            {"company_id": self.company.id, "date_from": "2026-08-01", "date_to": "2026-08-31"}
        )
        self.assertEqual(
            batch._get_or_create_arca_documents_folder(),
            batch._get_or_create_arca_documents_folder(),
        )

    def test_reprocess_reruns_comparison_from_stored_file(self):
        move = self._create_bill(
            self.partner_amx, self.doc_type_a, "9999-1", "2026-08-15", price_unit=500.0
        )
        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard.action_process()

        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        line_count_before = batch.line_count
        pending_line = batch.line_ids.filtered(lambda line: line.move_id == move)
        self.assertEqual(pending_line.result, "pending_in_arca")

        # Simulate the user fixing the bill's document number after seeing
        # it wrongly flagged, then reprocessing the same file instead of
        # re-uploading it.
        match_row = self._load_rows("mis_comprobantes_base.xlsx")[0]
        move.l10n_latam_document_number = "%s-%s" % (match_row["point_of_sale"], match_row["number_from"])
        batch.action_reprocess()

        self.assertEqual(batch.line_count, line_count_before - 1)
        new_line = batch.line_ids.filtered(lambda line: line.move_id == move)
        self.assertTrue(new_line)
        self.assertNotEqual(new_line.result, "pending_in_arca")

    def test_action_reprocess_multi_from_runs_list(self):
        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard.action_process()
        batch1 = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        wizard2 = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard2.action_process()
        batch2 = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        self.assertNotEqual(batch1, batch2)
        line_ids_before_1 = batch1.line_ids.ids
        line_ids_before_2 = batch2.line_ids.ids

        # Simulates selecting both runs in "My Vouchers - Runs" and using
        # the "Reprocess" entry in the Action menu.
        result = (batch1 | batch2).action_reprocess_multi()

        self.assertEqual(result, {"type": "ir.actions.client", "tag": "reload"})
        # _run_comparison() unlinks and recreates lines, so new ids prove
        # both runs actually reran rather than one being silently skipped.
        self.assertNotEqual(batch1.line_ids.ids, line_ids_before_1)
        self.assertNotEqual(batch2.line_ids.ids, line_ids_before_2)

    def test_action_reprocess_batches_from_line_selection(self):
        wizard = self._create_wizard("mis_comprobantes_base.xlsx")
        wizard.action_process()

        batch = self.env["arca.bill.comparison.batch"].search(
            [("company_id", "=", self.company.id)], order="id desc", limit=1
        )
        processed_on_before = batch.last_processed_on

        # Simulates selecting rows in the results grid and using the
        # "Reprocess" entry in the Action menu, instead of opening the run.
        result = batch.line_ids.action_reprocess_batches()
        self.assertEqual(result, {"type": "ir.actions.client", "tag": "reload"})
        self.assertGreater(batch.last_processed_on, processed_on_before)

    def test_reprocess_without_source_file_raises(self):
        batch = self.env["arca.bill.comparison.batch"].create(
            {"company_id": self.company.id, "date_from": "2026-08-01", "date_to": "2026-08-31"}
        )
        with self.assertRaises(UserError):
            batch.action_reprocess()

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
