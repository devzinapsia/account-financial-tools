Odoo uses the same wording for customers and vendors in several places of
the Invoicing / Accounting app, which reads confusingly in Spanish: a
customer invoice shows a "Pagar" (pay) button, and the Customers menu has
a "Pagos" (payments) entry, exactly like the vendor side. On the vendor
side, the credit notes menu is called "Reembolsos" (refunds).

This module changes those texts, customer side and vendor credit notes
only:

* **Invoice form**: the "Pay" button of customer invoices, credit notes
  and receipts is replaced by a "Collect" button ("Cobrar"). Vendor
  bills, refunds and receipts keep "Pay" ("Pagar"). Both buttons run the
  same action; only one of them is shown on each document.
* **Customer invoice and credit note lists**: the "Pay" header button
  becomes "Collect" ("Cobrar").
* **Gear (⚙) menu action of the invoice form**: renamed to "Pay / Collect"
  ("Pagar / Cobrar"), since Odoo can't show a different action name per
  document type.
* **Customers ‣ Payments** menu: renamed to "Collections" ("Cobros"), and
  its window title to "Customer Collections" ("Cobros de clientes").
* **Vendors ‣ Refunds** menu: renamed to "Credit Notes" ("Notas de
  crédito"), and its window title too.

Everything else on the vendor side (Vendors ‣ Payments, the bill lists,
etc.) is left untouched.

Technical notes
===============

* The menu and action renames change records that belong to the
  ``account`` module. Their Spanish texts are written with
  ``update_field_translations()`` from this module's own po files on every
  install/upgrade, because a regular translation load never replaces the
  translation ``account`` already set on those records.
* Uninstalling the module restores the original names ("Pay", "Payments",
  "Customer Payments", "Refunds") and their translations from
  ``account``'s po files.
* ``account_payment`` (installed automatically with ``account``) hides the
  "Pay" buttons while an invoice has an authorized online transaction. The
  glue module ``account_translation_improvements_account_payment``
  (installed automatically) applies the same rule to the "Collect"
  buttons.
* Modules that replace or hide the invoice's "Pay" buttons (for example
  third-party payment modules) may need a glue module to apply the same
  change to the "Collect" buttons.
