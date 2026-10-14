Glue module between ``account_translation_improvements`` and ingadhoc's
``account_ux``, installed automatically when both are installed.

``account_ux``'s **Customers Ledger** ("Mayor de Clientes") and **Vendors
Ledger** ("Mayor de Proveedores") open the same payment items list, whose
header button reads "Pay" ("Pagar") in both. With this module it reads
"Collect" ("Cobrar") in the Customers Ledger; the Vendors Ledger keeps
"Pay". The button runs the same action as before, only its label changes.

How it works
============

``account_translation_improvements`` shows "Collect" on that list when the
action opening it has ``collect_payment_items`` in its context. This
module adds that key to the context of ``account_ux``'s Customers Ledger
action (``account_ux.action_account_moves_customers_ledger``):

* Only that key is added; every other key of the action's context (its
  ``search_default_*`` filters, etc.) is kept as ``account_ux`` defines
  it. No ``account_ux`` code, view or file is changed.
* The ``search_default_trade_receivable`` key the action already has can't
  be used instead: the web client's search model turns ``search_default_*``
  keys into filters and removes them from the context before the list
  sees them.
* ``account_ux``'s own upgrade rewrites the action's context; this module
  depends on it, so it's upgraded right after and adds the key back.
* Uninstalling this module removes the key, leaving the action as
  ``account_ux`` defines it.
* Like any action context key, it's also passed on to what's opened from
  that list (e.g. the payment wizard), where nothing reads it.
