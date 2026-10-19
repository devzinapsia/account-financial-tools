This module enforces the ARCA (formerly AFIP) service billing period on
Argentinian customer invoices and credit notes.

ARCA requires the service period (start/end date) to be informed when an
invoice's concept is Services or Products and Services. Odoo's ``l10n_ar``
module already provides the ``l10n_ar_afip_service_start`` and
``l10n_ar_afip_service_end`` fields, but does not require them.

This module makes those two fields mandatory to confirm (post) an invoice,
whenever all of the following conditions are met on a given
``account.move``. The invoice can still be freely saved as a draft with
the dates empty; the check only blocks the confirm/post action:

- The invoice is a customer invoice or customer credit note
  (``move_type`` is ``out_invoice`` or ``out_refund``).
- Its journal is a sales journal.
- Its journal is an electronic ARCA point of sale (any AFIP POS System
  other than "Pre-printed Invoice").
- The journal has the new "Validate ARCA service period date entry" option
  enabled.
- The invoice's ARCA concept is Services or Products and Services.

The validation can be enabled or disabled per sales journal, so it only
applies where it is actually needed.

Two more options, scoped to the same electronic service invoices, let each
sales journal control how the service period is proposed and printed:

- **Default service period**: the period proposed on the invoice form as
  soon as the invoice date is set and the dates are still empty.

  - *Empty*: nothing is proposed, the user enters the dates.
  - *Invoice month* (default): first to last day of the invoice date's
    month.
  - *Invoice day*: the invoice date itself, as both start and end.

  Dates already entered by the user are never overwritten. If the dates
  are still empty when the invoice is confirmed (and their entry is not
  required), they are filled in with the invoice day when that option is
  selected, or with the invoice month otherwise (the standard ``l10n_ar``
  behavior), since ARCA requires them. This happens before the CAE is
  requested, so the dates sent to ARCA match the ones on the invoice.
- **Print service period on documents** (enabled by default): when
  disabled, the "Invoiced period" line is not printed on the invoice PDF.
  The period is still informed to ARCA.
