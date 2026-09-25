Glue module between ``account_translation_improvements`` and ingadhoc's
``account_payment_financial_surcharge``, installed automatically when both
are installed.

``account_payment_financial_surcharge`` changes the invoice form's "Pay"
buttons: they also show on draft invoices (only hidden once cancelled),
and they run ``action_force_register_payment`` with the
``open_invoice_payment`` context, which the financial surcharge flow
relies on. ``account_translation_improvements`` shows a "Collect" button
instead of "Pay" on customer documents. Without this module:

* "Collect" wouldn't get those changes, so customer invoices would lose
  the financial surcharge flow and couldn't be collected while in draft;
* depending on the order in which the modules were installed, the
  surcharge module could also show "Pay" on customer documents, next to
  "Collect".

This module applies the surcharge changes to the "Collect" buttons
(customer documents only) and sets the "Pay" buttons' condition again
(vendor documents only). Its view has a high priority so it's applied
after both modules, whatever the installation order.

Like the surcharge module itself, it replaces the visibility conditions
other modules add to these buttons (for example ``account_payment``'s
authorized online transactions), so "Pay" and "Collect" behave the same
way.
