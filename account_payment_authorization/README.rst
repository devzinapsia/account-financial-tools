==============================
Account Payment Authorization
==============================

Some users can load vendor bills and register payments for them, but
certain payments should not be confirmed without another user's approval
first -- for example, payments above a given amount, payments using a
sensitive payment method, or payments for bills with a particular
classification.

This module adds configurable **payment authorization schemes**. Each
scheme defines a set of conditions (invoice classification, vendor,
payment method, minimum amount) and a list of users allowed to authorize
a vendor payment matching those conditions. When a user tries to confirm
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
