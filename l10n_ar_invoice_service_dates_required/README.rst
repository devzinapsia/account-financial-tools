=========================================
L10n AR Invoice Service Dates Required
=========================================

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

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Journals**, open an electronic sales
journal, and enable **Validate ARCA service period date entry** in the
ARCA/AFIP configuration section. The option is only visible on sales
journals configured as an ARCA point of sale.

Usage
=====

Create or edit a customer invoice or credit note on a journal that has the
validation enabled. The invoice can be saved as a draft freely, even with
the **Service Date** fields (in the *Other Info* tab) left empty. When the
invoice's ARCA concept is Services or Products and Services (i.e. it has
service lines), those two fields must be filled in before the invoice can
be confirmed (posted); otherwise a validation error is raised at that
point.

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
