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
