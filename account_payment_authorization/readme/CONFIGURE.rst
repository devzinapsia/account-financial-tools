Go to **Accounting ‣ Configuration ‣ Invoicing ‣ Payment Authorization
Schemes** and create a scheme.

Every filter field on a scheme is optional. Leaving a field empty means
that condition does not restrict the scheme -- a scheme with every field
left empty matches any vendor payment (a catch-all scheme). A scheme
matches a payment when **all** of its non-empty conditions are satisfied:

* **Company**: leave empty to apply the scheme to every company.
* **Invoice classification**: requires the ``account_move_classification``
  module. Matches payments for a vendor bill with this classification.
* **Vendors**: matches payments to any of the selected vendors.
* **Payment method**: matches payments using this payment method.
* **Minimum amount**: matches payments whose amount is greater than or
  equal to this value.
* **Authorized users**: the users allowed to approve a payment matching
  this scheme. If a scheme matches a payment but has no authorized users
  configured, that payment can never be approved by anyone -- this is
  intentional, not a bug: it is a way to permanently block a category of
  payments until someone is added to the scheme.

If a payment matches more than one scheme at the same time, it is enough
for the payment to be approved by **any** authorized user from **any** of
the matching schemes (the set of allowed approvers is the union across
all matching schemes, not their intersection).
