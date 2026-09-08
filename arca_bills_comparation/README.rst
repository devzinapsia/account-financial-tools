=======================
ARCA Bills Comparison
=======================

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

**Table of contents**

.. contents::
   :local:

Configuration
=============

No specific configuration is required beyond the standard Argentinian
localization setup:

- The ``l10n_ar`` module must be installed.
- Purchase journals that should be compared must have **Use Documents**
  enabled (**Accounting ‣ Configuration ‣ Journals ‣ Journal ‣ Advanced
  Settings**).
- The current company's Tax ID (**Settings ‣ Companies**) must match the
  CUIT used to download the ARCA export, since the file's recipient CUIT is
  validated against it before importing.

Access to the wizard and its results follows the same security groups as
vendor bills: ``Billing`` users can run the process and view results;
``Accounting Manager`` users additionally get full read/write access to
stored runs and lines.

Usage
=====

Go to **Accounting ‣ Review ‣ ARCA ‣ My Vouchers**.

1. Download the "Mis Comprobantes Recibidos" export from ARCA's web portal
   for the desired period, either as Excel (``.xlsx``) or CSV.
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
Vouchers - Runs**) so past comparisons remain available for reference. Runs
are only created by processing a file through this wizard, so that list has
no **New** button of its own. The imported file itself is also kept, filed
under **Documents ‣ Zinapsia ‣ Mis comprobantes ARCA**, and the run record
shows when it was last processed.

After fixing issues a run flagged (e.g. a wrong vendor or document number
on a bill), open that run and click **Reprocess** to compare against the
same file again without downloading/uploading it a second time; this
discards and rebuilds that run's results. **Reprocess** is also available
from the **Actions** (⚙) menu on both **My Vouchers - Runs** (select one or
more runs directly) and the results grid (select rows from one or more
runs), so several runs can be reprocessed at once without opening each one
individually.

Field mapping
-------------

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
-----------

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
- Matching runs in three passes, from strictest to loosest, each only
  applied to what the previous pass left unmatched. A match found on the
  second or third pass is always reported as "Difference" (never
  "Match"), with a note on which key disagreed:

  1. Voucher type + point of sale/number range + issuer VAT (the normal
     case).
  2. Same point of sale/number range/issuer VAT, ignoring voucher type —
     real bookkeeping sometimes records a bill under a different but
     related document type than the one ARCA registered for it (observed
     case: ARCA reports "81 - Tique Factura A", the bill was entered in
     Odoo as "1 - Factura A").
  3. Same point of sale/number range only, ignoring both voucher type and
     issuer VAT, **but only accepted when the total amount also agrees**
     — a mismatched CUIT usually means the bill was booked against the
     wrong (often related) vendor in Odoo (observed case: an invoice from
     "Telecom Personal S.A." booked against "Telecom Argentina S.A.").
     Point of sale/number alone is too weak a key to trust on its own, so
     without the amount also matching, this pass is skipped and both
     sides are left as separate Pending lines instead of risking a false
     pairing between two unrelated vendors.
- The "Net amounts"/"Taxes" columns and their soft-field comparison
  always show the *combined* total (ARCA's "Neto Gravado Total" + "Neto
  No Gravado" + "Op. Exentas" for the net amount, "Total IVA" + "Otros
  Tributos" for taxes) rather than each raw ARCA column alone, so a
  "Pending in ARCA" line (built from the Odoo bill's own
  ``amount_untaxed``/``amount_tax``, which don't separate those out)
  shows a value on the same basis as an ARCA-sourced line.
- "Pending in ARCA" lines show the voucher type as "``<code>`` -
  ``<Title Cased name>``" (e.g. "1 - Factura A") to visually match ARCA's
  own formatting, even though there is no real ARCA text for that line —
  ``l10n_latam.document.type.name`` is stored in all caps internally
  (e.g. "FACTURAS A").
- The results list has no form view: there is nothing useful to show on
  a comparison line's own record, so opening one would just be an extra
  click for no benefit. Each row has an "Open bill" button (only when a
  vendor bill is linked) that jumps straight to it instead.
- Row color follows severity, not the order results are usually reviewed
  in: green for "Match", amber for "Difference" (something exists on
  both sides but disagrees), red for "Pending in Odoo" (ARCA reported a
  voucher with no matching bill at all), blue for "Pending in ARCA".
- Some document types have no point of sale component at all (e.g.
  "Facturas y Comprobantes del Exterior" for foreign suppliers), so the
  accountant types the vendor's own document number freely instead of
  Odoo's usual "PPPPP-NNNNNNNN" sequence. These bills can't be matched
  against a point of sale/number key and always show as "Pending in
  ARCA"; the **Point of sale** column is left blank and the **Number**
  columns show the full document number as entered, instead of blank
  columns.
- The CSV export carries the same data as the Excel one, but with
  different header text, ``;`` as the field separator, ISO (``YYYY-MM-DD``)
  dates instead of ``DD/MM/YYYY``, and AFIP's own numeric codes instead of
  text for "Tipo de Comprobante" (e.g. ``1`` instead of ``1 - Factura A``)
  and the issuer/recipient identification type (e.g. ``80`` instead of
  ``CUIT``). The file format is picked from the uploaded filename's
  extension. Numeric identification type codes are mapped to their name
  (only the ones this tool's matching logic cares about have an entry: 80
  CUIT, 86 CUIL, 87 CDI, 96 DNI); anything else is kept as the raw code.
  A bare numeric voucher type is looked up against
  ``l10n_latam.document.type`` so the grid always shows "``<code>`` -
  ``<Name>``" regardless of which file format was imported.
- The imported file is stored as a ``documents.document`` under a fixed
  **Zinapsia / Mis comprobantes ARCA** folder path (created automatically
  the first time it's needed, reused afterwards — never duplicated). Both
  folders are created without an owner so they show up as a shared
  "Company" folder for every user instead of looking privately owned by
  whoever ran the first import; the file itself is owned by the user who
  ran the wizard.
- **Reprocess** re-parses that same stored file and re-runs the full
  comparison, discarding the run's previous result lines first (so it's
  safe to click more than once). It requires the stored file to still be
  there — deleting it from Documents (or the run predating this feature,
  when no file was stored yet) leaves nothing to reprocess and raises an
  error instead of silently doing nothing.
- The stored file's name is prefixed with the run's own date range (e.g.
  "2026-08-01 - 2026-08-31 - <original filename>"), since ARCA's own
  export always uses the same filename regardless of period, which would
  otherwise make every run's file indistinguishable from another in
  Documents.
- The results grid opens with ``target: "main"``, clearing any existing
  breadcrumb, instead of inheriting whichever page happened to be open
  behind the "My Vouchers" wizard dialog (a modal has no breadcrumb entry
  of its own to attach to).
- Deleting a run also sends its stored file to the Documents trash
  (archived, not hard-deleted — recoverable from there like any other
  manually deleted document), instead of leaving an orphaned file behind
  with nothing pointing to it.

Roadmap
-------

This module is designed to host more ARCA control processes in the future,
comparing other exports. Also planned for the "My Vouchers" process itself,
not implemented in this version:

- An **Import Pending in Odoo** button that automatically registers vendor
  bills for "Pending in Odoo" lines, using the vendor's default accounts
  from ``account_partner_defaults`` when installed (falling back to
  journal/general defaults otherwise), leaving the bill posted when every
  field matches ARCA or as a draft otherwise.

Bug Tracker
===========

Bugs are tracked on
`GitHub Issues <https://github.com/devzinapsia/account-financial-tools/issues>`_.
In case of trouble, please check there if your issue has already been
reported.

Credits
=======

Authors
-------

* Zinapsia

Maintainers
-----------

This module is maintained by Zinapsia.

This module is part of the
`account-financial-tools <https://github.com/devzinapsia/account-financial-tools>`_
project.
