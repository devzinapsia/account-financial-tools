Reviewers
---------

Pick them in **Accounting ‣ Configuration ‣ Settings ‣ Vendor Payments ‣
Payment review ‣ Payment reviewers**, or, equivalently, open each user in
**Settings ‣ Users & Companies ‣ Users** and, under **Accounting**, set
**Payment review** to *Payment reviewer*. Both edit the same access right,
which applies to every company. A reviewer only needs read access to
accounting: the group implies the read-only accounting profile, and
reviewing never requires rights to modify payments.

Review settings
---------------

Go to **Accounting ‣ Configuration ‣ Settings ‣ Vendor Payments ‣ Payment
review** (per company):

* **Payment review**: enables the circuit. Vendor payments confirmed from
  then on start as *Pending review*, unless an exemption applies.
* **Review from amount**: vendor payments below this amount, in company
  currency, start as *Not required*. Leave it at 0 to review payments of
  any amount.
* **Payments that don't require review**: conditions built with Odoo's
  filter editor, e.g. *Journal = Petty cash* or a given vendor. Matching
  payments start as *Not required*. Leave it empty for no exemption.
* **Days to answer observations**: deadline of the activity assigned to
  the issuer when the reviewer records observations (3 by default).

Exemptions are evaluated once, when a payment is confirmed: changing them
does not reclassify payments already confirmed. A reviewer can still
review any *Not required* payment on purpose, or mark pending ones as
*Not required* from the review wizard.

Vendor payments confirmed before the module was installed start as *Not
required*, so the circuit applies from the installation onwards.
