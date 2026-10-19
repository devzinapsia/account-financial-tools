Some users load and confirm vendor bills, but certain bills should not be
paid without another user's approval first -- for example, bills above a
given amount, bills from a sensitive vendor, or bills with a particular
classification.

This module adds configurable **vendor bill authorization policies**. Each
policy defines a set of conditions on the bill (any field: classification,
vendor, journal, amount...) and a list of users allowed to authorize a bill
matching those conditions. A bill matching at least one policy can be
confirmed as usual, but it **can't be paid** until one of those users has
authorized it. A policy can also be marked **Always block**, so that
matching bills can never be confirmed at all.

The flow has three separable steps:

#. Whoever loads the bill confirms it. If it matches a policy, it is left
   *To authorize* and the authorizers are notified.
#. An authorizer reviews it and **authorizes** it, or **rejects** it with
   a reason.
#. Once authorized, whoever is in charge of payments **pays** it, as
   usual.

**Scope: vendor bills and vendor credit/debit notes only** (journal entries
of type *Vendor Bill* / *Vendor Credit Note*, i.e. ``in_invoice`` and
``in_refund``; vendor debit notes are ``in_invoice`` bills). Customer
invoices and credit notes, purchase receipts, and miscellaneous journal
entries are never affected, whatever the policies say.

This module is independent from *Autorización de pagos a proveedores*
(``account_payment_authorization``), which applies a similar pattern to
vendor payments: either one can be installed without the other. When
ingadhoc's ``account_payment_pro`` is installed, the bridge module
*Autorización de facturas de proveedor - Payment Pro* installs
automatically and applies the same rules to its payment receipts.
