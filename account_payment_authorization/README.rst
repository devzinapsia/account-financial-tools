==============================
Account Payment Authorization
==============================

Some users can load vendor bills and register payments for them, but
certain payments should not be confirmed without another user's approval
first -- for example, payments above a given amount, payments using a
sensitive payment method, or payments for bills with a particular
classification.

This module adds configurable **payment authorization schemes**. Each
scheme defines a domain condition on the payment (evaluated on
``account.payment``, including the linked vendor bill) and a list of
users allowed to authorize a vendor payment matching that condition, or
is flagged to always block a matching payment outright. When a user tries
to confirm
a vendor payment that matches at least one scheme, and that user is not
themselves listed as an authorizer on any matching scheme, the payment is
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
Schemes** and create a scheme. Clicking a row opens its form.

A scheme has:

* **Company**: leave empty to apply the scheme to every company.
* **Conditions**: a domain built with Odoo's standard filter editor,
  evaluated against the vendor payment (``account.payment``). An empty
  domain matches any vendor payment (a catch-all scheme). Any field on the
  payment can be used, including the linked vendor bill through
  ``authorization_invoice_id``, e.g.:

  * ``authorization_invoice_id.classification_id`` -- requires the
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

Usage
=====

Registering a payment
----------------------

Open a vendor bill and click **Register Payment** as usual (or select a
single vendor bill from the Vendor Bills list and use the same action).

* If the payment does not match any authorization scheme, or the user
  registering it is already an authorized user on every matching scheme,
  the payment is confirmed immediately, exactly as before this module was
  installed.
* If the payment matches at least one scheme and the user registering it
  is **not** an authorized user on any matching scheme, the payment is
  **not** confirmed. Instead:

  * Its **Authorization status** is set to *To authorize*.
  * An activity is assigned to every authorized user of every matching
    scheme, so it shows up in their **My Activities** and triggers an
    email according to their own notification preferences.
  * A message is logged on the payment's chatter noting that
    authorization was requested and from whom.
  * The user who tried to confirm the payment gets an error message
    explaining that the payment is now pending authorization.

Approving or rejecting a pending payment
------------------------------------------

Open the payment (it will be in the *To authorize* state) and go to its
**Authorization** tab. If you are one of the users authorized to approve
it, you will see **Approve** and **Reject** buttons there.

* **Approve**: confirms the payment right away, sets the **Authorized
  by** field to you, and marks the pending activities as done.
* **Reject**: opens a small window asking for a reason. Once confirmed,
  the payment's **Authorization status** becomes *Rejected*, the reason
  is stored on the payment, the pending activities are marked done, and
  an activity is created for the user who originally registered the
  payment, informing them of the rejection and the reason.

Only users who are actually listed as authorizers on a matching scheme
can approve or reject a payment -- this is enforced on the server, not
just by hiding the buttons.

Finding pending payments
--------------------------

The **Vendor Payments** list (Accounting ‣ Vendors ‣ Payments) offers two
extra filters in the search bar:

* **To authorize**: payments currently waiting for any authorization.
* **To authorize by me**: payments you are personally allowed to
  approve or reject right now.

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
