Go to **Accounting ‣ Configuration ‣ Invoicing ‣ Vendor bill authorization
policies** (accounting administrators only) and create a policy. Clicking
a row opens its form.

A policy has:

* **Company**: defaults to your current company when creating a new
  policy; leave it empty to apply the policy to every company instead.
* **Conditions**: a domain built with Odoo's standard filter editor,
  evaluated against the vendor bill (``account.move``) when it is
  confirmed. An empty domain matches any vendor bill or vendor
  credit/debit note (a catch-all policy). A new policy's domain starts
  pre-filled with **Type is in Vendor Bill, Vendor Credit Note**, which
  keeps the record count shown while editing the domain accurate. Don't
  add a condition on the bill's **Status**: policies are evaluated while
  the bill is being confirmed. Any other field of the bill can be used,
  e.g.:

  * ``classification_id`` -- matches bills with (or without) a given
    classification (see the *Account Move Classification* module). To
    match bills that have *no* classification at all, filter on
    "Classification" "is not set".
  * ``partner_id`` -- matches bills from specific vendors.
  * ``journal_id`` -- matches bills in a specific purchase journal.
  * ``amount_total`` -- matches bills by total amount. Combine several
    policies with ``amount_total`` conditions to build tiers, e.g. one
    policy for ``amount_total < 1000`` authorized by user A, another for
    ``1000 <= amount_total < 5000`` authorized by users B and C, and
    another for ``amount_total >= 5000`` authorized by user D.

* **Always block**: if checked, any bill matching this policy's conditions
  can never be **confirmed** by anyone, regardless of the Authorizers field
  (which is then ignored and hidden) and regardless of any other matching
  policy. Use this to explicitly and permanently deny a category of bills
  -- e.g. a policy with the condition "classification is not set" and
  Always block checked means vendor bills without a classification can
  never be confirmed.
* **Authorizers**: the users allowed to authorize the payment of a bill
  matching this policy (ignored if Always block is checked). If a policy
  matches a bill but has no authorizers configured and Always block is not
  checked, that bill can never be authorized, nor paid, by anyone -- it
  usually means the field was left empty by mistake.

If a bill matches more than one policy at the same time, it is enough for
the bill to be authorized by **any** authorized user from **any** of the
matching (non-blocking) policies (the set of allowed approvers is the
union across all matching policies, not their intersection) -- unless at
least one of the matching policies has Always block checked, in which case
the bill can't be confirmed at all.

Whether a bill requires authorization is decided **when it is confirmed**:
changing the policies afterwards does not affect bills that were already
confirmed (nor bills confirmed before this module was installed).
