=================================================
Período de servicio ARCA en facturas electrónicas
=================================================

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

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Journals**, open an electronic sales
journal, and in the ARCA/AFIP configuration section set:

- **Validate ARCA service period date entry**: require the service period
  dates to confirm the invoice.
- **Default service period**: *Empty*, *Invoice month* (default) or
  *Invoice day*.
- **Print service period on documents**: uncheck it to hide the invoiced
  period on the printed invoice.

These options are only visible on sales journals configured as an ARCA
point of sale, and only apply to electronic (non pre-printed) journals.

Usage
=====

Create or edit a customer invoice or credit note on a journal that has the
validation enabled. The invoice can be saved as a draft freely, even with
the **Service Date** fields (in the *Other Info* tab) left empty. When the
invoice's ARCA concept is Services or Products and Services (i.e. it has
service lines), those two fields must be filled in before the invoice can
be confirmed (posted); otherwise a validation error is raised at that
point.

When the journal proposes a default period, setting the invoice date on a
draft service invoice fills in the **Service Date** fields with the invoice
month or the invoice day, as configured, provided they are still empty.
They can be changed freely before confirming.

When the journal is set not to print the service period, the printed
invoice omits the "Invoiced period" line.

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
