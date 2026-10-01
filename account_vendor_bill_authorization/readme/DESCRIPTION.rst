Some users load vendor bills, but certain bills should not be confirmed
without another user's approval first -- for example, bills above a given
amount, bills from a sensitive vendor, or bills with a particular
classification.

This module adds configurable **vendor bill authorization policies**. Each
policy defines a set of conditions on the bill (any field: classification,
vendor, journal, amount...) and a list of users allowed to authorize a bill
matching those conditions. A draft bill matching at least one policy can
only be confirmed once one of those users has authorized it; a policy can
also be marked **Always block**, so that matching bills can never be
confirmed at all.

The flow has three separable steps:

#. Whoever loads the bill leaves it in draft (and may try to confirm it,
   which is refused and notifies the authorizers).
#. An authorizer reviews it and **authorizes** it (without confirming it),
   or **rejects** it with a reason.
#. Then whoever loaded the bill, the authorizer, or anyone else allowed to
   confirm bills, **confirms** it.

Authorizers also get an **Authorize + Confirm** button that does steps 2
and 3 in a single click.

**Scope: vendor bills and vendor credit/debit notes only** (journal entries
of type *Vendor Bill* / *Vendor Credit Note*, i.e. ``in_invoice`` and
``in_refund``). Customer invoices and credit notes, purchase receipts, and
miscellaneous journal entries are never affected, whatever the policies
say.

This module is independent from *Autorización de pagos a proveedores*
(``account_payment_authorization``), which applies the same pattern to
vendor payments: either one can be installed without the other.
