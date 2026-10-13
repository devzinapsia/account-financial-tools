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
  then on start as *Pending review*, if they meet the conditions below.
* **Review from amount**: vendor payments below this amount, in company
  currency, start as *Not required*. Leave it at 0 to review payments of
  any amount.
* **Payments that require review**: conditions built with Odoo's filter
  editor, e.g. *Journal in (the journals of a given bank)*. Only matching
  payments start as *Pending review*; the rest start as *Not required*.
  Leave it empty to review every vendor payment.
* **Days to answer observations**: deadline of the activity assigned to
  the issuer when the reviewer records observations (3 by default).

The amount and the conditions are evaluated once, when a payment is
confirmed: changing them does not reclassify payments already confirmed.
A reviewer can still review any *Not required* payment on purpose, or
mark pending ones as *Not required* from the review wizard, e.g. the ones
confirmed before the conditions were adjusted, so they leave the
*Payments to review* list without being signed off as reviewed.

Resetting a payment to draft takes it out of the circuit: its review
status, reviewer, comment, answer and pending review activities are
cleared, since the payment may be changed before it's confirmed again.
On the next confirmation it's evaluated as a new payment, with the
current settings. The previous decisions stay in the chatter.

Vendor payments confirmed before the module was installed start as *Not
required*, so the circuit applies from the installation onwards.
