from odoo import _, api, fields, models
from odoo.tools.misc import format_date

from ..tools.arca_xlsx_parser import normalize_vat, resolve_currency_code, split_document_number

AMOUNT_TOLERANCE = 0.02


def _format_point_of_sale(value):
    return "%05d" % value if value is not None else ""


def _format_number(value):
    return "%08d" % value if value is not None else ""


class ArcaBillComparisonBatch(models.Model):
    _name = "arca.bill.comparison.batch"
    _description = "ARCA Bill Comparison Batch"
    _order = "create_date desc"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, default=lambda self: self.env.company
    )
    date_from = fields.Date(string="From", required=True, readonly=True)
    date_to = fields.Date(string="To", required=True, readonly=True)
    user_id = fields.Many2one(
        "res.users", string="Processed by", default=lambda self: self.env.user, readonly=True
    )
    line_ids = fields.One2many("arca.bill.comparison.line", "batch_id", readonly=True)
    line_count = fields.Integer(compute="_compute_line_count")

    @api.depends("date_from", "date_to")
    def _compute_name(self):
        for batch in self:
            if batch.date_from and batch.date_to:
                batch.name = _("My Vouchers %(date_from)s - %(date_to)s") % {
                    "date_from": format_date(self.env, batch.date_from),
                    "date_to": format_date(self.env, batch.date_to),
                }
            else:
                batch.name = _("My Vouchers")

    @api.depends("line_ids")
    def _compute_line_count(self):
        for batch in self:
            batch.line_count = len(batch.line_ids)

    def action_view_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "arca_bills_comparation.action_arca_bill_comparison_line"
        )
        action["domain"] = [("batch_id", "=", self.id)]
        action["context"] = {"search_default_group_by_result": 1}
        return action

    def _run_comparison(self, rows):
        """Compare parsed ARCA rows against this batch's vendor bills and create the result lines."""
        self.ensure_one()
        candidate_moves = self._get_candidate_moves()
        move_index = self._index_moves(candidate_moves)
        move_index_by_issuer = self._index_moves_by_issuer(candidate_moves)
        move_index_by_pos = self._index_moves_by_point_of_sale(candidate_moves)

        consumed_move_ids = set()
        unmatched_rows = []
        line_values = []
        for row in rows:
            key = self._match_key(
                row["voucher_type_code"], row["point_of_sale"], row["issuer_id_type"], row["issuer_vat"]
            )
            moves = self._find_matching_moves(move_index, key, row, consumed_move_ids)
            if moves:
                consumed_move_ids.update(moves.ids)
                result, detail = self._compare_soft_fields(row, moves)
                # Only one move can be linked from a result line; when ARCA
                # grouped several consecutive invoices into a single ranged
                # row, all matched moves are aggregated for the soft-field
                # comparison above and excluded from "Pending in ARCA" below,
                # but the line itself links to the first (lowest-numbered)
                # one as a representative reference.
                line_values.append(self._prepare_line_from_row(row, moves[:1], result, detail))
            else:
                unmatched_rows.append(row)

        # Fallback pass, ignoring voucher type: real bookkeeping sometimes
        # records a bill under a different (but related) document type than
        # the one ARCA registered for the same issuer/point of sale/number
        # (e.g. ARCA reports "81 - Tique Factura A" but the bill was entered
        # in Odoo as "1 - Factura A"). Without this, both sides would show
        # up as disconnected "Pending" lines instead of a linked Difference
        # that calls out the type mismatch.
        still_unmatched_rows = []
        for row in unmatched_rows:
            issuer_key = self._issuer_key(row["point_of_sale"], row["issuer_id_type"], row["issuer_vat"])
            moves = self._find_matching_moves(move_index_by_issuer, issuer_key, row, consumed_move_ids)
            if moves:
                consumed_move_ids.update(moves.ids)
                line_values.append(self._prepare_line_from_row(row, moves[:1], "difference", self._type_mismatch_detail(row, moves)))
            else:
                still_unmatched_rows.append(row)

        # Second fallback pass, ignoring issuer VAT too (same point of sale
        # and number range only): a wrong vendor on the Odoo bill is a rarer
        # mistake than a type mismatch, but also an easy one to make between
        # related companies (e.g. a bill from "Telecom Personal S.A." booked
        # against "Telecom Argentina S.A." in Odoo) and an easy one to spot
        # once flagged. To avoid pairing up bills from two unrelated vendors
        # that happen to share a point of sale/number by coincidence, a
        # candidate here is only accepted when its total amount also agrees
        # with ARCA's, so the match is never accepted on number alone.
        for row in still_unmatched_rows:
            moves = self._find_matching_moves(move_index_by_pos, row["point_of_sale"], row, consumed_move_ids)
            moves = moves.filtered(lambda move: abs(move.amount_total - row["total_amount"]) <= AMOUNT_TOLERANCE)
            if moves:
                consumed_move_ids.update(moves.ids)
                detail = self._issuer_mismatch_detail(row, moves)
                if row["voucher_type_code"] not in moves.mapped("l10n_latam_document_type_id.code"):
                    detail = "\n".join(filter(None, [self._type_mismatch_detail(row, moves), detail]))
                line_values.append(self._prepare_line_from_row(row, moves[:1], "difference", detail))
            else:
                line_values.append(
                    self._prepare_line_from_row(row, self.env["account.move"], "pending_in_odoo", "")
                )

        pending_in_arca_moves = candidate_moves.filtered(
            lambda move: move.id not in consumed_move_ids
            and move.invoice_date
            and self.date_from <= move.invoice_date <= self.date_to
        )
        for move in pending_in_arca_moves:
            line_values.append(self._prepare_line_from_move(move))

        self.env["arca.bill.comparison.line"].create(line_values)

    def _get_candidate_moves(self):
        moves = self.env["account.move"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "!=", "cancel"),
                ("journal_id.type", "=", "purchase"),
                ("journal_id.l10n_latam_use_documents", "=", True),
            ]
        )
        # l10n_latam_document_number is a computed, non-stored field, so it
        # can't be used in the search domain above; filter it in Python.
        return moves.filtered("l10n_latam_document_number")

    @staticmethod
    def _match_key(voucher_type_code, point_of_sale, issuer_id_type, issuer_vat):
        return (
            (voucher_type_code or "").strip(),
            point_of_sale,
            (issuer_id_type or "").strip().upper(),
            normalize_vat(issuer_vat),
        )

    @staticmethod
    def _issuer_key(point_of_sale, issuer_id_type, issuer_vat):
        """Same as _match_key but without voucher type, for the type-agnostic fallback pass."""
        return (
            point_of_sale,
            (issuer_id_type or "").strip().upper(),
            normalize_vat(issuer_vat),
        )

    def _index_moves(self, moves):
        """Group moves by (type, point of sale, issuer), so each ARCA row is a single dict lookup."""
        index = {}
        for move in moves:
            point_of_sale, number = split_document_number(move.l10n_latam_document_number)
            if point_of_sale is None:
                continue
            key = self._match_key(
                move.l10n_latam_document_type_id.code,
                point_of_sale,
                move.partner_id.l10n_latam_identification_type_id.name,
                move.partner_id.vat,
            )
            index.setdefault(key, []).append((move, number))
        return index

    def _index_moves_by_issuer(self, moves):
        """Same as _index_moves, keyed without voucher type, for the type-agnostic fallback pass."""
        index = {}
        for move in moves:
            point_of_sale, number = split_document_number(move.l10n_latam_document_number)
            if point_of_sale is None:
                continue
            key = self._issuer_key(
                point_of_sale,
                move.partner_id.l10n_latam_identification_type_id.name,
                move.partner_id.vat,
            )
            index.setdefault(key, []).append((move, number))
        return index

    def _index_moves_by_point_of_sale(self, moves):
        """Index purely by point of sale, for the last-resort fallback pass.

        Ignores both voucher type and issuer, so callers must gate any match
        found through this index on another strong signal (the total amount)
        before accepting it — point of sale/number alone is too weak a key
        on its own, since two unrelated vendors can plausibly reuse the same
        combination.
        """
        index = {}
        for move in moves:
            point_of_sale, number = split_document_number(move.l10n_latam_document_number)
            if point_of_sale is None:
                continue
            index.setdefault(point_of_sale, []).append((move, number))
        return index

    def _type_mismatch_detail(self, row, moves):
        odoo_types = sorted(set(moves.mapped("l10n_latam_document_type_id.name")))
        return _("Voucher type: ARCA %(arca)s vs Odoo %(odoo)s") % {
            "arca": row["voucher_type_raw"],
            "odoo": ", ".join(odoo_types),
        }

    def _issuer_mismatch_detail(self, row, moves):
        odoo_issuers = sorted(
            "%s (%s)" % (name, vat) for name, vat in set(zip(moves.mapped("partner_id.name"), moves.mapped("partner_id.vat")))
        )
        return _("Issuer: ARCA %(arca_name)s (%(arca_vat)s) vs Odoo %(odoo)s") % {
            "arca_name": row["issuer_name"],
            "arca_vat": row["issuer_vat"],
            "odoo": ", ".join(odoo_issuers),
        }

    def _find_matching_moves(self, move_index, key, row, consumed_move_ids):
        """Return every move whose number falls in the row's range, lowest number first.

        Usually a single move. When ARCA groups several consecutive invoices
        from the same issuer into one ranged row, this can be more than one;
        callers must aggregate them for the soft-field comparison rather than
        treat each independently. Moves already consumed by an earlier row are
        excluded, so a single bill is never linked from more than one result
        line even if two ARCA rows' ranges happen to overlap.
        """
        candidates = move_index.get(key, [])
        matches = sorted(
            (
                pair
                for pair in candidates
                if pair[0].id not in consumed_move_ids and row["number_from"] <= pair[1] <= row["number_to"]
            ),
            key=lambda pair: pair[1],
        )
        return self.env["account.move"].concat(*(move for move, _number in matches))

    def _compare_soft_fields(self, row, moves):
        diffs = []

        arca_currency_code = resolve_currency_code(row["currency_raw"])
        odoo_currency_codes = sorted(set(moves.currency_id.mapped("name")))
        if arca_currency_code is None:
            diffs.append(_("Currency: unrecognized ARCA symbol '%s'") % row["currency_raw"])
        elif odoo_currency_codes != [arca_currency_code]:
            diffs.append(
                _("Currency: ARCA %(arca)s vs Odoo %(odoo)s")
                % {"arca": arca_currency_code, "odoo": ", ".join(odoo_currency_codes)}
            )

        odoo_dates = sorted({move_date for move_date in moves.mapped("invoice_date") if move_date})
        if odoo_dates != [row["date"]]:
            diffs.append(
                _("Date: ARCA %(arca)s vs Odoo %(odoo)s")
                % {"arca": row["date"], "odoo": ", ".join(d.isoformat() for d in odoo_dates)}
            )

        odoo_total = sum(moves.mapped("amount_total"))
        arca_total = row["total_amount"]
        if abs(arca_total - odoo_total) > AMOUNT_TOLERANCE:
            diffs.append(
                _("Total amount: ARCA %(arca).2f vs Odoo %(odoo).2f")
                % {"arca": arca_total, "odoo": odoo_total}
            )

        odoo_tax = sum(moves.mapped("amount_tax"))
        arca_tax = row["total_vat"] + row["other_taxes"]
        # ARCA sometimes reports every breakdown column as zero for vouchers
        # with no VAT at all (e.g. certain exempt insurance premiums), while
        # Odoo still books the full amount as untaxed base. When neither side
        # reports any VAT, only the total (already checked above) is
        # meaningful; comparing the untaxed/tax split would flag a false
        # difference driven purely by that reporting quirk.
        has_vat = abs(arca_tax) > AMOUNT_TOLERANCE or abs(odoo_tax) > AMOUNT_TOLERANCE

        if has_vat:
            odoo_untaxed = sum(moves.mapped("amount_untaxed"))
            arca_untaxed = row["untaxed_total"] + row["non_taxed_amount"] + row["exempt_operations"]
            if abs(arca_untaxed - odoo_untaxed) > AMOUNT_TOLERANCE:
                diffs.append(
                    _("Net amounts: ARCA %(arca).2f vs Odoo %(odoo).2f")
                    % {"arca": arca_untaxed, "odoo": odoo_untaxed}
                )

            if abs(arca_tax - odoo_tax) > AMOUNT_TOLERANCE:
                diffs.append(
                    _("Taxes: ARCA %(arca).2f vs Odoo %(odoo).2f")
                    % {"arca": arca_tax, "odoo": odoo_tax}
                )

        if diffs:
            return "difference", "\n".join(diffs)
        return "match", ""

    def _prepare_line_from_row(self, row, move, result, detail):
        values = {("arca_%s" % key): value for key, value in row.items()}
        values["arca_point_of_sale"] = _format_point_of_sale(row["point_of_sale"])
        values["arca_number_from"] = _format_number(row["number_from"])
        values["arca_number_to"] = _format_number(row["number_to"])
        # Displayed (and compared) as combined totals rather than the raw
        # "Total IVA"/"Neto Gravado Total" columns alone, so this matches
        # what "Pending in ARCA" lines show (computed from Odoo's own
        # amount_untaxed/amount_tax, which don't separate out "Otros
        # Tributos"/"Neto No Gravado"/"Op. Exentas") and what the soft-field
        # comparison above actually checks.
        values["arca_untaxed_total"] = row["untaxed_total"] + row["non_taxed_amount"] + row["exempt_operations"]
        values["arca_total_vat"] = row["total_vat"] + row["other_taxes"]
        arca_currency_code = resolve_currency_code(row["currency_raw"])
        currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", arca_currency_code)], limit=1)
            if arca_currency_code
            else self.env["res.currency"]
        )
        values.update(
            {
                "batch_id": self.id,
                "move_id": move.id if move else False,
                "result": result,
                "difference_detail": detail,
                "arca_currency_id": (currency or self.company_id.currency_id).id,
            }
        )
        return values

    @staticmethod
    def _format_voucher_type(document_type):
        """Match ARCA's own "<code> - <Title Case Name>" style (e.g. "1 - Factura A").

        l10n_latam.document.type.name is stored in ALL CAPS (e.g. "FACTURAS
        A"); this is only used for "Pending in ARCA" lines, which have no
        real ARCA text to show, so it's just a display approximation.
        """
        if not document_type:
            return ""
        name = (document_type.name or "").title()
        return "%s - %s" % (document_type.code, name) if document_type.code else name

    def _prepare_line_from_move(self, move):
        point_of_sale, number = split_document_number(move.l10n_latam_document_number)
        if point_of_sale is None:
            # Some document types (e.g. "Facturas y Comprobantes del
            # Exterior") have no point of sale component; the number is a
            # free-form value entered by the accountant instead of Odoo's
            # usual "PPPPP-NNNNNNNN" sequence. Show it as-is rather than
            # leaving the column blank.
            point_of_sale_display = ""
            number_display = move.l10n_latam_document_number or ""
        else:
            point_of_sale_display = _format_point_of_sale(point_of_sale)
            number_display = _format_number(number)
        return {
            "batch_id": self.id,
            "move_id": move.id,
            "result": "pending_in_arca",
            "difference_detail": "",
            "arca_date": move.invoice_date,
            "arca_voucher_type_raw": self._format_voucher_type(move.l10n_latam_document_type_id),
            "arca_voucher_type_code": move.l10n_latam_document_type_id.code,
            "arca_point_of_sale": point_of_sale_display,
            "arca_number_from": number_display,
            "arca_number_to": number_display,
            "arca_authorization_code": "",
            "arca_issuer_id_type": move.partner_id.l10n_latam_identification_type_id.name or "",
            "arca_issuer_vat": move.partner_id.vat or "",
            "arca_issuer_name": move.partner_id.name or "",
            "arca_recipient_id_type": "",
            "arca_recipient_vat": "",
            "arca_exchange_rate": 0.0,
            "arca_currency_raw": move.currency_id.name or "",
            "arca_untaxed_total": move.amount_untaxed,
            "arca_non_taxed_amount": 0.0,
            "arca_exempt_operations": 0.0,
            "arca_other_taxes": 0.0,
            "arca_total_vat": move.amount_tax,
            "arca_total_amount": move.amount_total,
            "arca_currency_id": move.currency_id.id,
        }
