Go to **Accounting ‣ Configuration ‣ Invoicing ‣ Payment Authorization
Schemes** and create a scheme. Clicking a row opens its form.

A scheme has:

* **Company**: defaults to your current company when creating a new
  scheme; leave it empty to apply the scheme to every company instead.
* **Conditions**: a domain built with Odoo's standard filter editor,
  evaluated against the vendor payment (``account.payment``). An empty
  domain matches any vendor payment (a catch-all scheme). A new scheme's
  domain starts pre-filled with **Payment type = Send**, **Recipient type
  = Vendor**, and **Pending confirmation = set** -- this module never
  actually evaluates a scheme outside those conditions, so keeping them
  keeps the record count shown while editing the domain accurate; remove
  any of them if you really mean to build a domain that reads as broader.
  Any field on the payment can be used, including the linked vendor bill
  through "Invoices" (``invoice_ids``, the field shown as "Facturas" in
  the filter editor when Spanish is active), e.g.:

  * ``invoice_ids.classification_id`` -- requires the
    ``account_move_classification`` module; matches bills with (or
    without) a given classification. To match bills that have *no*
    classification at all, filter on "Classification" "is not set".
  * ``partner_id`` -- matches payments to specific vendors.
  * ``payment_method_line_id`` -- matches payments using a specific
    payment method.
  * ``amount`` -- matches payments by amount. Combine several schemes with
    ``amount`` conditions to build tiers, e.g. one scheme for
    ``0 <= amount < 1000`` authorized by user A, another for
    ``1000 <= amount < 2000`` authorized by users B and C, and another for
    ``amount >= 2000`` authorized by user D.
  * ``is_pending_confirmation`` ("Pending confirmation") -- prefer this
    over the payment's own "Status" field when a condition needs to
    target payments still awaiting confirmation. The "Register Payment"
    wizard can set Status to "In process" before the payment is actually
    confirmed, so a condition on Status = Draft can fail to match a
    payment that is genuinely still pending; Pending confirmation is
    based on the underlying journal entry instead and does not have that
    problem.

* **Always block**: if checked, any payment matching this scheme's
  conditions can never be approved by anyone, regardless of the
  Authorized users field (which is then ignored and hidden). Use this to
  explicitly and permanently deny a category of payments -- e.g. a scheme
  with the condition "classification is not set" and Always block checked
  means vendor bills without a classification can never be paid.
* **Authorized users**: the users allowed to approve a payment matching
  this scheme (ignored if Always block is checked). If a scheme matches a
  payment but has no authorized users configured and Always block is not
  checked, that payment can also never be approved by anyone -- same
  practical effect as Always block, but it usually means the field was
  left empty by mistake rather than on purpose. Prefer checking Always
  block when that is the actual intent, so the scheme documents itself.

If a payment matches more than one scheme at the same time, it is enough
for the payment to be approved by **any** authorized user from **any** of
the matching (non-blocking) schemes (the set of allowed approvers is the
union across all matching schemes, not their intersection) -- unless at
least one of the matching schemes has Always block checked, in which case
the payment can never be approved regardless of what the other matching
schemes allow.
