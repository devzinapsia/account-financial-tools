This module enforces the ARCA (formerly AFIP) service billing period on
Argentinian customer invoices and credit notes.

ARCA requires the service period (start/end date) to be informed when an
invoice's concept is Services or Products and Services. Odoo's ``l10n_ar``
module already provides the ``l10n_ar_afip_service_start`` and
``l10n_ar_afip_service_end`` fields, but does not require them.

This module makes those two fields mandatory, both visually (in the form
view) and at the data level (create/write), whenever all of the following
conditions are met on a given ``account.move``:

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
