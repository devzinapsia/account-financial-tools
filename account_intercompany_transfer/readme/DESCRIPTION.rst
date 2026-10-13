Moves money from a bank or cash journal of one company to a bank or cash
journal of **another, independent company of the same database** (not a
branch of the same company), through a bridge account configured in each
company.

Each transfer is a document (``ICT/2026/00001``) created from a wizard. It
creates and posts, in one single transaction, two real payments:

* **Origin company**: an outgoing payment in the origin journal.
* **Destination company**: an incoming payment in the destination journal.

Each payment uses its own company's bridge account as counterpart, and the
other company's partner as contact. If anything fails in either company
(e.g. a closed period), nothing is created in any of them.

Accounting flow
---------------

Example: 10,000 from *Cash A* (company A) to *Cash B* (company B).

Company A, outgoing payment ``PCSH1/2026/00001``, contact *Company B*:

=====================================  ==========  ==========
Account                                Debit       Credit
=====================================  ==========  ==========
Intercompany bridge account of A       10,000
Outstanding payments of *Cash A*                   10,000
=====================================  ==========  ==========

Company B, incoming payment ``PCSH2/2026/00001``, contact *Company A*:

=====================================  ==========  ==========
Account                                Debit       Credit
=====================================  ==========  ==========
Outstanding receipts of *Cash B*       10,000
Intercompany bridge account of B                   10,000
=====================================  ==========  ==========

The cash/bank account itself is only moved when each payment is reconciled
with its bank statement line, as for any other payment. Posting the
transfer directly against the bank account would count the money twice
once the statement arrives, since every statement line creates its own
liquidity line.

Balances between companies
--------------------------

The bridge account of each company accumulates its position with every
other company, and the contact of each journal item is the other company.
Grouping the bridge account's journal items (or its general ledger) by
partner shows, per pair of companies, what was sent and received; the
balance of A against *Company B* is the mirror of the balance of B against
*Company A*.

Numbering
---------

* Transfers: own numbering per company, ``ICT/<year>/<number>``, drawn by
  the **origin** company. The year is the transfer date's, and a failed
  transfer leaves no gap.
* Payments: the regular payment numbering of each journal, like any other
  payment. Both payments reference the transfer number in their memo
  (``ICT/2026/00001 - <memo>``).

Limitations
-----------

* Both journals must have the same currency (the journal's own currency,
  or its company's). There is no currency conversion nor exchange
  difference in this version.
* The manual payment method of both journals must have an outstanding
  account.
* The date can't fall inside a closed period of either company.

Difference with other internal transfers
----------------------------------------

* **Odoo's internal transfers** and **ingadhoc's** ``account_internal_transfer``
  (*Accounting > Bank and Cash > Transfers*) move money between journals of
  the same company or of its branches, through the single *Internal
  Transfer* account of Odoo's settings.
* **Intercompany transfers** move money between independent companies,
  each one with its own bridge account, a separate setting that never
  reads nor changes Odoo's *Internal Transfer* account.

Both processes are kept fully apart, in both directions. The payments of an
intercompany transfer carry none of the fields Odoo or ingadhoc use to
recognize an internal transfer (internal transfer flag, destination
journal, paired payment, Odoo's transfer account): they never show up in
ingadhoc's *Transfers* list, filters or report, and their numbering is not
affected. The other way round, the intercompany transfers list and wizard
only work with intercompany transfer documents, and a payment carrying an
internal transfer marker can never be linked to one. Intercompany payments
are regular payments, so they do show up in the standard customer payments
list, where they are reconciled.
