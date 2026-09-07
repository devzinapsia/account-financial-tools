Go to **Accounting ‣ Review ‣ ARCA ‣ My Vouchers**.

1. Download the "Mis Comprobantes Recibidos" Excel file from ARCA's web
   portal for the desired period.
2. Attach it in the **File to import** field. The **From**/**To** dates are
   proposed automatically from the first and last voucher dates found in the
   file (ARCA's export only lists days with activity, so this may differ
   from what you originally requested); adjust them if needed.
3. Click **Process**.

If the file's recipient CUIT does not match the current company's Tax ID,
the import is stopped before creating any record and an error is shown.

Otherwise, a grouped list of results opens, one row per ARCA voucher (or per
unmatched Odoo bill), showing the same columns as the ARCA file plus the
**Result** and, for the "Difference" outcome, the specific fields and
values that disagree. Use **Group By ‣ Result** (active by default) to
review each outcome separately, and the list view's own **Export** action
to get an ``.xlsx`` copy.

Each run is kept as a run record (**Accounting ‣ Review ‣ ARCA ‣ My
Vouchers - Runs**) so past comparisons remain available for reference.

Field mapping
~~~~~~~~~~~~~

======================================  ====================================
ARCA column                             Odoo field
======================================  ====================================
Fecha                                   ``account.move.invoice_date``
Tipo (code before the dash)             ``l10n_latam_document_type_id.code``
Punto de Venta                          prefix of
                                         ``l10n_latam_document_number``
Número Desde / Número Hasta             suffix of
                                         ``l10n_latam_document_number``
                                         (matches if it falls inside the
                                         range)
Tipo Doc. Emisor                        ``partner_id.l10n_latam_identification
                                         _type_id.name``
Nro. Doc. Emisor                        ``partner_id.vat``
Moneda                                  ``currency_id.name`` (via a symbol →
                                         ISO code table, since Odoo's own
                                         currency symbol is ``$`` for both
                                         ARS and USD)
Imp. Total                              ``amount_total``
Neto Gravado Total + Neto No Gravado +
Op. Exentas                             ``amount_untaxed``
Total IVA + Otros Tributos              ``amount_tax``
======================================  ====================================

``Nro. Doc. Receptor`` is only used to validate the file belongs to the
current company; it is not compared per voucher. The per-rate VAT breakdown
columns are imported and shown (hidden by default) but are not part of the
comparison logic, since a discrepancy there already surfaces through the
totals above.

Assumptions
~~~~~~~~~~~

- Amounts are compared with a 0.02 tolerance to absorb rounding differences.
- The Odoo universe considered is every non-cancelled vendor bill/refund
  (draft included) on a purchase journal with "Use Documents" enabled, that
  already has a document number assigned.
- CAE and CUIT values, which can exceed Odoo's 32-bit ``Integer`` field
  range, are stored as text and only parsed to numbers in memory for
  comparison.
- The company-mismatch error message is kept in the exact Spanish wording
  requested for this process, instead of following the module's usual
  English-source-plus-translation convention.
- When one ARCA row groups several consecutive invoices from the same
  issuer into a single Número Desde/Hasta range, every Odoo bill whose
  number falls in that range is aggregated (amounts summed) for the
  comparison, so none of them is wrongly reported as "Pending in ARCA".
  The result line links to the first (lowest-numbered) bill as a
  reference. If two ARCA rows' ranges overlap (a data-quality issue on
  ARCA's side), a bill already linked to an earlier row is never linked
  again from a later one.
- Point of sale and voucher number are stored zero-padded (5 and 8 digits
  respectively, matching ``l10n_ar``'s own formatting) as text, so they
  display and sort correctly instead of picking up Odoo's Integer
  thousands-separator formatting and losing leading zeros.
- When a voucher carries no VAT on either side (ARCA's ``Total IVA`` +
  ``Otros Tributos`` and Odoo's ``amount_tax`` both zero), only the total
  amount is compared; the untaxed/tax breakdown is skipped. ARCA
  sometimes reports every breakdown column as zero for such vouchers
  (observed on exempt insurance premiums) even though the total is
  correct, and Odoo still books the full amount as untaxed base — that
  reporting quirk would otherwise show up as a false "Difference".

Roadmap
~~~~~~~

This module is designed to host more ARCA control processes in the future,
comparing other exports. Also planned for the "My Vouchers" process itself,
not implemented in this version:

- An **Import Pending in Odoo** button that automatically registers vendor
  bills for "Pending in Odoo" lines, using the vendor's default accounts
  from ``account_partner_defaults`` when installed (falling back to
  journal/general defaults otherwise), leaving the bill posted when every
  field matches ARCA or as a draft otherwise.
