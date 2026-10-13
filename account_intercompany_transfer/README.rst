===========================
Transferencias intercompany
===========================

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
===============

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
==========================

The bridge account of each company accumulates its position with every
other company, and the contact of each journal item is the other company.
Grouping the bridge account's journal items (or its general ledger) by
partner shows, per pair of companies, what was sent and received; the
balance of A against *Company B* is the mirror of the balance of B against
*Company A*.

Numbering
=========

* Transfers: own numbering per company, ``ICT/<year>/<number>``, drawn by
  the **origin** company. The year is the transfer date's, and a failed
  transfer leaves no gap.
* Payments: the regular payment numbering of each journal, like any other
  payment. Both payments reference the transfer number in their memo
  (``ICT/2026/00001 - <memo>``).

Limitations
===========

* Both journals must have the same currency (the journal's own currency,
  or its company's). There is no currency conversion nor exchange
  difference in this version.
* The manual payment method of both journals must have an outstanding
  account.
* The date can't fall inside a closed period of either company.

Difference with other internal transfers
========================================

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

**Table of contents**

.. contents::
   :local:

Configuration
=============

Bridge account of each company
------------------------------

Every company that sends or receives intercompany transfers needs its own
bridge account. Settings are per company, so configure each one
separately: select the company in the company switcher, then go to
**Accounting ‣ Configuration ‣ Settings ‣ Default Accounts ‣ Bank
transactions and payments ‣ Intercompany transfer bridge account**, save,
and repeat for the next company.

The bridge account must:

* belong to that company and be active;
* be a *Current Assets* or *Current Liabilities* account (bank, cash,
  receivable, payable, income, expense and equity accounts are rejected);
* not be the outstanding account of any payment method of the company's
  journals.

It is a setting of its own: it doesn't use nor change Odoo's *Internal
Transfer* account. Reconciliation doesn't need to be allowed on it.

Journals
--------

Only bank and cash journals can be used. The **manual** payment method of
each journal (*Incoming Payments* and *Outgoing Payments* tabs of the
journal) must have an outstanding account, which is where the payment is
posted until it's reconciled with the bank statement.

Access rights
-------------

Open the user in **Settings ‣ Users & Companies ‣ Users** and, under
**Accounting**, set **Intercompany transfers** to *User*. This access
right is granted to specific users only: no other access right includes
it, administrators included.

The payments of a transfer are created with the user's own access rights
in both companies, so the user also needs:

* both companies among their **allowed companies** (they don't need to be
  ticked in the company switcher);
* accounting access (at least *Invoicing*) in both companies.

Numbering
---------

The ``ICT`` numbering of each company is created automatically when the
module is installed and when a new company is created.

Usage
=====

Making a transfer
-----------------

#. Go to **Accounting ‣ Accounting ‣ Transactions ‣ Intercompany
   transfers** (under **Accounting ‣ Bank and Cash** when ingadhoc's
   internal transfers are installed, see the bridge module
   ``account_intercompany_transfer_adhoc``) and click **New transfer**.
#. Pick the **origin journal**: the origin company and the currency follow
   from it.
#. Pick the **destination company** and the **destination journal**: only
   companies with a bridge account, and journals in the same currency as
   the origin journal, are offered.
#. Enter the **amount**, the **date** and an optional **memo**, and click
   **Confirm**.

The transfer opens posted, with a smart button to each payment. Each
payment is then reconciled with its bank statement line in its own
company, as any other payment. Opening the payment of a company that is
not ticked in the company switcher asks to select that company first.

The memo is the only field of a transfer that can be changed. Its payments
and their journal entries can't be modified, reset to draft, cancelled,
reversed nor deleted by hand: cancel the transfer instead.

Cancelling a transfer
---------------------

Click **Cancel** on a posted transfer: both payments are cancelled, in
both companies, in one single transaction, and the transfer becomes
*Cancelled*. It is not possible when:

* any journal item of either payment is reconciled, typically with a bank
  statement line: undo that reconciliation first;
* either payment is dated in a closed period of its company.

The message names the payment, its company and the reason. A cancelled
transfer can't be posted again: create a new one.

Finding transfers
-----------------

The transfers list can be filtered by status and by **Sent by the current
company** / **Received by the current company**, and grouped by origin
company, destination company, status or month. Each user sees the
transfers where the origin or the destination company is among their
allowed companies.

In the payments lists, the **Intercompany transfer** column (optional) and
search field show which transfer a payment belongs to.

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
