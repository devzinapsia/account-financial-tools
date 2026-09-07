import csv
import datetime
import io
import re
import unicodedata
from io import BytesIO

import openpyxl

from odoo import _

# Real header row of ARCA's "Mis Comprobantes Recibidos" xlsx export (row 2
# of the sheet; row 1 is a merged title cell). Order matters: it is paired
# positionally with FIELD_KEYS below.
EXPECTED_HEADERS_XLSX = [
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

# Real header row of ARCA's "Mis Comprobantes Recibidos" csv export. Same
# data as the xlsx export, but with different header text, a single header
# row (no merged title row), ";" as the field separator, ISO dates, and
# numeric AFIP codes instead of text for "Tipo de Comprobante"/identification
# type columns (handled in _parse_row / _resolve_identification_type below).
EXPECTED_HEADERS_CSV = [
    "Fecha de Emisión",
    "Tipo de Comprobante",
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
    "Imp. Neto Gravado IVA 0%",
    "IVA 2,5%",
    "Imp. Neto Gravado IVA 2,5%",
    "IVA 5%",
    "Imp. Neto Gravado IVA 5%",
    "IVA 10,5%",
    "Imp. Neto Gravado IVA 10,5%",
    "IVA 21%",
    "Imp. Neto Gravado IVA 21%",
    "IVA 27%",
    "Imp. Neto Gravado IVA 27%",
    "Imp. Neto Gravado Total",
    "Imp. Neto No Gravado",
    "Imp. Op. Exentas",
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

# AFIP's own numeric "Tipo de Documento" codes, used by the csv export for
# the issuer/recipient identification type columns instead of the text
# labels the xlsx export uses (e.g. "80" instead of "CUIT"). Only the types
# this tool's matching logic cares about need a real name; anything else is
# left as the raw numeric code, same graceful-degradation approach as
# CURRENCY_SYMBOL_TO_ISO above.
AFIP_IDENTIFICATION_TYPE_CODES = {
    "80": "CUIT",
    "86": "CUIL",
    "87": "CDI",
    "96": "DNI",
}


class ArcaFileFormatError(Exception):
    """Raised when an ARCA export doesn't match the expected format."""


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


def parse_arca_file(content, filename=None):
    """Parse an ARCA "Mis Comprobantes Recibidos" export (xlsx or csv).

    :param content: raw bytes of the file.
    :param filename: original filename, used to pick the parser (".csv" is
        parsed as csv; anything else is parsed as the original xlsx export).
    :return: list of row dicts, keyed by FIELD_KEYS.
    :raises ArcaFileFormatError: if the file can't be read or is missing
        expected columns.
    """
    if (filename or "").lower().strip().endswith(".csv"):
        return _parse_csv_file(content)
    return _parse_xlsx_file(content)


def _parse_xlsx_file(content):
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

    column_index = _build_column_index(header_row, EXPECTED_HEADERS_XLSX)

    rows = []
    for raw_row in rows_iter:
        if raw_row is None or all(cell is None for cell in raw_row):
            continue
        rows.append(_parse_row(raw_row, column_index))
    return rows


def _parse_csv_file(content):
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ArcaFileFormatError(
            _("The file could not be read as a valid CSV (UTF-8) file.")
        ) from exc

    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows_iter = iter(reader)

    header_row = next(rows_iter, None)
    if header_row is None:
        raise ArcaFileFormatError(_("The file is missing the column headers row."))

    column_index = _build_column_index(header_row, EXPECTED_HEADERS_CSV)

    rows = []
    for raw_row in rows_iter:
        if not raw_row or all(not (cell or "").strip() for cell in raw_row):
            continue
        rows.append(_parse_row(raw_row, column_index))
    return rows


def _build_column_index(header_row, expected_headers):
    header_map = {}
    for idx, value in enumerate(header_row):
        header_map[_normalize_header(value)] = idx

    expected_normalized = [_normalize_header(header) for header in expected_headers]
    missing = [
        header
        for header, normalized in zip(expected_headers, expected_normalized)
        if normalized not in header_map
    ]
    if missing:
        raise ArcaFileFormatError(
            _("The file is missing expected columns: %s") % ", ".join(missing)
        )

    return {key: header_map[normalized] for key, normalized in zip(FIELD_KEYS, expected_normalized)}


def _normalize_header(value):
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().lower()


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
        "issuer_id_type": _resolve_identification_type(get("issuer_id_type")),
        "issuer_vat": _to_str(get("issuer_vat")),
        "issuer_name": _to_str(get("issuer_name")),
        "recipient_id_type": _resolve_identification_type(get("recipient_id_type")),
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
    for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise ArcaFileFormatError(_("Unrecognized date format: %s") % text)


def _extract_voucher_type_code(value):
    if value is None:
        return ""
    match = re.match(r"\s*(\d+)", str(value))
    return match.group(1) if match else ""


def _resolve_identification_type(value):
    """Map an AFIP numeric identification type code (csv export) to its name.

    The xlsx export already gives the text name (e.g. "CUIT"); this is a
    no-op for it since those values are never purely numeric.
    """
    text = _to_str(value)
    return AFIP_IDENTIFICATION_TYPE_CODES.get(text, text) if text.isdigit() else text


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
