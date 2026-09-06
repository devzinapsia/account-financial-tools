import datetime
import re
import unicodedata
from io import BytesIO

import openpyxl

from odoo import _

# Real header row of ARCA's "Mis Comprobantes Recibidos" export (row 2 of the
# sheet; row 1 is a merged title cell). Order matters: it is paired
# positionally with FIELD_KEYS below.
EXPECTED_HEADERS = [
    "Fecha",
    "Tipo",
    "Punto de Venta",
    "Número Desde",
    "Número Hasta",
    "Cód. Autorización",
    "Tipo Doc. Emisor",
    "Nro. Doc. Emisor",
    "Denominación Emisor",
    "Tipo Doc. Receptor",
    "Nro. Doc. Receptor",
    "Tipo Cambio",
    "Moneda",
    "Neto Grav. IVA 0%",
    "IVA 2,5%",
    "Neto Grav. IVA 2,5%",
    "IVA 5%",
    "Neto Grav. IVA 5%",
    "IVA 10,5%",
    "Neto Grav. IVA 10,5%",
    "IVA 21%",
    "Neto Grav. IVA 21%",
    "IVA 27%",
    "Neto Grav. IVA 27%",
    "Neto Gravado Total",
    "Neto No Gravado",
    "Op. Exentas",
    "Otros Tributos",
    "Total IVA",
    "Imp. Total",
]

FIELD_KEYS = [
    "date",
    "voucher_type_raw",
    "point_of_sale",
    "number_from",
    "number_to",
    "authorization_code",
    "issuer_id_type",
    "issuer_vat",
    "issuer_name",
    "recipient_id_type",
    "recipient_vat",
    "exchange_rate",
    "currency_raw",
    "untaxed_vat_0",
    "vat_2_5",
    "untaxed_vat_2_5",
    "vat_5",
    "untaxed_vat_5",
    "vat_10_5",
    "untaxed_vat_10_5",
    "vat_21",
    "untaxed_vat_21",
    "vat_27",
    "untaxed_vat_27",
    "untaxed_total",
    "non_taxed_amount",
    "exempt_operations",
    "other_taxes",
    "total_vat",
    "total_amount",
]

AMOUNT_FIELD_KEYS = FIELD_KEYS[13:]

# ARCA's own web export shows the currency as a plain symbol, not the AFIP
# 3-letter code used in the electronic invoicing webservices (that one lives
# on res.currency.l10n_ar_afip_code, e.g. "PES"/"DOL"). Map ARCA's symbols to
# ISO codes so they can be compared against account.move.currency_id.name.
# Extend this table if a client's export shows other currency symbols.
CURRENCY_SYMBOL_TO_ISO = {
    "$": "ARS",
    "u$s": "USD",
    "us$": "USD",
    "u$d": "USD",
}


class ArcaFileFormatError(Exception):
    """Raised when an ARCA xlsx file doesn't match the expected format."""


def normalize_vat(value):
    """Strip everything but digits, so '30-71897208-2' and 30718972082 compare equal."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value))


def resolve_currency_code(raw_symbol):
    """Map an ARCA currency symbol (e.g. '$') to an ISO code (e.g. 'ARS').

    Returns None when the symbol isn't in CURRENCY_SYMBOL_TO_ISO.
    """
    key = (raw_symbol or "").strip().lower()
    return CURRENCY_SYMBOL_TO_ISO.get(key)


def split_document_number(document_number):
    """Split an Odoo l10n_latam_document_number ('00005-00000303') into (point_of_sale, number) ints.

    Returns (None, None) if the value doesn't match the expected pattern
    (e.g. no document number assigned yet).
    """
    if not document_number:
        return None, None
    match = re.match(r"^\s*(\d+)-(\d+)\s*$", str(document_number))
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_arca_file(content):
    """Parse an ARCA "Mis Comprobantes Recibidos" xlsx export.

    :param content: raw bytes of the .xlsx file.
    :return: list of row dicts, keyed by FIELD_KEYS.
    :raises ArcaFileFormatError: if the file can't be read or is missing
        expected columns.
    """
    try:
        workbook = openpyxl.load_workbook(BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:
        raise ArcaFileFormatError(
            _("The file could not be read as a valid Excel (.xlsx) file.")
        ) from exc

    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)

    next(rows_iter, None)  # row 1: merged title cell, ignored

    header_row = next(rows_iter, None)
    if header_row is None:
        raise ArcaFileFormatError(_("The file is missing the column headers row."))

    header_map = {}
    for idx, value in enumerate(header_row):
        header_map[_normalize_header(value)] = idx

    missing = [
        header
        for header, normalized in zip(EXPECTED_HEADERS, _EXPECTED_HEADERS_NORMALIZED)
        if normalized not in header_map
    ]
    if missing:
        raise ArcaFileFormatError(
            _("The file is missing expected columns: %s") % ", ".join(missing)
        )

    column_index = {
        key: header_map[normalized]
        for key, normalized in zip(FIELD_KEYS, _EXPECTED_HEADERS_NORMALIZED)
    }

    rows = []
    for raw_row in rows_iter:
        if raw_row is None or all(cell is None for cell in raw_row):
            continue
        rows.append(_parse_row(raw_row, column_index))
    return rows


def _normalize_header(value):
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().lower()


_EXPECTED_HEADERS_NORMALIZED = [_normalize_header(header) for header in EXPECTED_HEADERS]


def _parse_row(raw_row, column_index):
    def get(key):
        idx = column_index[key]
        return raw_row[idx] if idx < len(raw_row) else None

    row = {
        "date": _parse_date(get("date")),
        "voucher_type_raw": _to_str(get("voucher_type_raw")),
        "voucher_type_code": _extract_voucher_type_code(get("voucher_type_raw")),
        "point_of_sale": _to_int(get("point_of_sale")),
        "number_from": _to_int(get("number_from")),
        "number_to": _to_int(get("number_to")),
        "authorization_code": _to_str(get("authorization_code")),
        "issuer_id_type": _to_str(get("issuer_id_type")),
        "issuer_vat": _to_str(get("issuer_vat")),
        "issuer_name": _to_str(get("issuer_name")),
        "recipient_id_type": _to_str(get("recipient_id_type")),
        "recipient_vat": _to_str(get("recipient_vat")),
        "currency_raw": _to_str(get("currency_raw")),
    }
    for key in ("exchange_rate",) + tuple(AMOUNT_FIELD_KEYS):
        row[key] = _to_float(get(key))
    return row


def _parse_date(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError as exc:
        raise ArcaFileFormatError(_("Unrecognized date format: %s") % text) from exc


def _extract_voucher_type_code(value):
    if value is None:
        return ""
    match = re.match(r"\s*(\d+)", str(value))
    return match.group(1) if match else ""


def _to_str(value):
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value):
    if value in (None, ""):
        return 0
    if isinstance(value, str):
        value = value.strip().replace(".", "").replace(",", "")
        return int(value) if value else 0
    return int(value)


def _to_float(value):
    if value in (None, ""):
        return 0.0
    if isinstance(value, str):
        value = value.strip().replace(".", "").replace(",", ".")
        return float(value) if value else 0.0
    return float(value)
