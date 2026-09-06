This module adds the "My Vouchers" ("Mis Comprobantes") control process, the
first of a planned family of ARCA (formerly AFIP) reconciliation tools. It
compares the "Mis Comprobantes Recibidos" (My Vouchers Received) export
downloaded from ARCA against the vendor bills (``account.move``,
``in_invoice``/``in_refund``) recorded in Odoo.

For each purchase journal with "Use Documents" enabled
(``account.journal.l10n_latam_use_documents``), every voucher informed by
ARCA is matched against Odoo by voucher type, point of sale, document number
(including ARCA's grouped number ranges) and issuer CUIT, and classified as:

- **Match**: found in Odoo and all amounts/date/currency agree.
- **Difference**: found in Odoo but at least one field disagrees (detailed on
  the result line).
- **Pending in Odoo**: informed by ARCA but no matching vendor bill exists
  yet.
- **Pending in ARCA**: a vendor bill exists in the period but was not
  informed by ARCA.

Results are grouped by outcome and can be exported to Excel using Odoo's
native list export.
