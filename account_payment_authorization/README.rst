==============================
Account Payment Authorization
==============================

Some users can load vendor bills and register payments for them, but
certain payments should not be confirmed without another user's approval
first -- for example, payments above a given amount, payments using a
sensitive payment method, or payments for bills with a particular
classification.

This module adds configurable **payment authorization policies**. Each
policy defines a set of conditions (invoice classification, vendor,
payment method, minimum amount) and a list of users allowed to authorize
a vendor payment matching those conditions. When a user tries to confirm
a vendor payment that matches at least one policy, and that user is not
themselves listed as an authorizer on any matching policy, the payment is
held in a "To authorize" state instead of being confirmed, and an
activity is created for each authorized user so they can review and
approve or reject it.

This feature only applies to a payment covering a single vendor bill,
created through the standard "Register Payment" wizard. Payments for
customers, internal transfers, and grouped payments covering more than
one bill are never affected.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Invoicing ‣ Payment Authorization
Policies** and create a policy. Clicking a row opens its form.

A policy has:

* **Company**: defaults to your current company when creating a new
  policy; leave it empty to apply the policy to every company instead.
* **Conditions**: a domain built with Odoo's standard filter editor,
  evaluated against the vendor payment (``account.payment``). An empty
  domain matches any vendor payment (a catch-all policy). A new policy's
  domain starts pre-filled with **Payment type = Send**, **Recipient type
  = Vendor**, and **Pending confirmation = set** -- this module never
  actually evaluates a policy outside those conditions, so keeping them
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
  * ``amount`` -- matches payments by amount. Combine several policies with
    ``amount`` conditions to build tiers, e.g. one policy for
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

* **Always block**: if checked, any payment matching this policy's
  conditions can never be approved by anyone, regardless of the
  Authorizers field (which is then ignored and hidden). Use this to
  explicitly and permanently deny a category of payments -- e.g. a policy
  with the condition "classification is not set" and Always block checked
  means vendor bills without a classification can never be paid.
* **Authorizers**: the users allowed to approve a payment matching this
  policy (ignored if Always block is checked). If a policy matches a
  payment but has no authorizers configured and Always block is not
  checked, that payment can also never be approved by anyone -- same
  practical effect as Always block, but it usually means the field was
  left empty by mistake rather than on purpose. Prefer checking Always
  block when that is the actual intent, so the policy documents itself.

If a payment matches more than one policy at the same time, it is enough
for the payment to be approved by **any** authorized user from **any** of
the matching (non-blocking) policies (the set of allowed approvers is the
union across all matching policies, not their intersection) -- unless at
least one of the matching policies has Always block checked, in which case
the payment can never be approved regardless of what the other matching
policies allow.

Usage
=====

Registering a payment
----------------------

Open a vendor bill and click **Register Payment** as usual (or select a
single vendor bill from the Vendor Bills list and use the same action).

* If the payment does not match any authorization policy, or the user
  registering it is already an authorized user on every matching policy,
  the payment is confirmed immediately, exactly as before this module was
  installed.
* If the payment matches at least one policy and the user registering it
  is **not** an authorized user on any matching policy, the payment is
  **not** confirmed. Instead:

  * Its **Authorization status** is set to *To authorize*.
  * An activity is assigned to every authorized user of every matching
    policy, so it shows up in their **My Activities** and triggers an
    email according to their own notification preferences.
  * A message is logged on the payment's chatter noting that
    authorization was requested and from whom.
  * The user who tried to confirm the payment gets an error message
    explaining that the payment is now pending authorization.

Authorizing or rejecting a pending payment
----------------------------------------------

Open the payment. If you are one of the users authorized to act on it,
you will see an **Authorize** button next to **Confirm** in the header,
and a **Reject** button in the **Authorization** tab -- available as soon
as the payment is a draft that matches a policy you can act on, even if
nobody has attempted to confirm it yet. It is not necessary to wait for
someone else to first try **Confirm** and be blocked from it (which is
what sets the **Authorization status** to *To authorize*): this matters
because, in practice, the person who registers the payment is often not
themselves an authorized user, so they could never be the one to trigger
that state.

* **Authorize**: does *not* confirm the payment. It only sets the
  **Authorization status** to *Authorized* and the **Authorized by**
  field to you, marks the pending activities as done, and logs it on the
  chatter. The payment stays in *Draft*.

  Once a payment is authorized this way, **anyone** with the normal
  permission to confirm payments can click the regular **Confirm**
  button to actually post it -- it no longer needs to be an authorized
  user, since the authorization already happened. This lets the person
  who signs off on a payment be different from the person who actually
  executes it.

  As a shortcut, if the user confirming the payment is themselves an
  authorized user for a matching policy, clicking **Confirm** directly
  (without using **Authorize** first) still authorizes and confirms it
  in one step, exactly as before.

  Authorized by mistake? While the payment is still a draft (i.e. not
  confirmed yet), an **Unauthorize** button appears next to **Confirm**.
  It reverts the **Authorization status** back to *To authorize*, clears
  **Authorized by**, logs it on the chatter, and notifies the user who
  originally registered the payment. The payment can be authorized again
  afterwards, by the same or a different authorizer, with no
  restriction.
* **Reject**: opens a small window asking for a reason. Once confirmed,
  the payment's **Authorization status** becomes *Rejected*, the reason
  is stored on the payment, the pending activities are marked done, and
  an activity is created for the user who originally registered the
  payment, informing them of the rejection and the reason.

Only users who are actually listed as authorizers on a matching policy
can authorize or reject a payment -- this is enforced on the server, not
just by hiding the buttons. Every authorization event (who authorized,
who confirmed, who rejected and why) is logged on the payment's chatter,
timestamped.

Finding pending payments
--------------------------

The **Vendor Payments** list (Accounting ‣ Vendors ‣ Payments) offers
extra filters in the search bar:

* **To authorize**: payments currently waiting for any authorization.
* **To authorize by me**: payments you are personally allowed to
  approve or reject right now.
* **Authorized, not confirmed by me yet**: payments you registered
  yourself that needed authorization, already got it, and are still
  sitting as a draft waiting to be confirmed -- easy to lose track of
  among other drafts otherwise, since nothing else singles them out
  once they are no longer *To authorize*.

The **Authorization status** column is also available (hidden by
default; enable it from the column selector).

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
