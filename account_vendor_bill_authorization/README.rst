=====================================
Autorización de facturas de proveedor
=====================================

Some users load vendor bills, but certain bills should not be confirmed
without another user's approval first -- for example, bills above a given
amount, bills from a sensitive vendor, or bills with a particular
classification.

This module adds configurable **vendor bill authorization policies**. Each
policy defines a set of conditions on the bill (any field: classification,
vendor, journal, amount...) and a list of users allowed to authorize a bill
matching those conditions. A draft bill matching at least one policy can
only be confirmed once one of those users has authorized it; a policy can
also be marked **Always block**, so that matching bills can never be
confirmed at all.

The flow has three separable steps:

#. Whoever loads the bill leaves it in draft (and may try to confirm it,
   which is refused and notifies the authorizers).
#. An authorizer reviews it and **authorizes** it (without confirming it),
   or **rejects** it with a reason.
#. Then whoever loaded the bill, the authorizer, or anyone else allowed to
   confirm bills, **confirms** it.

Authorizers also get an **Authorize + Confirm** button that does steps 2
and 3 in a single click.

**Scope: vendor bills and vendor credit/debit notes only** (journal entries
of type *Vendor Bill* / *Vendor Credit Note*, i.e. ``in_invoice`` and
``in_refund``). Customer invoices and credit notes, purchase receipts, and
miscellaneous journal entries are never affected, whatever the policies
say.

This module is independent from *Autorización de pagos a proveedores*
(``account_payment_authorization``), which applies the same pattern to
vendor payments: either one can be installed without the other.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Invoicing ‣ Vendor bill authorization
policies** (accounting administrators only) and create a policy. Clicking
a row opens its form.

A policy has:

* **Company**: defaults to your current company when creating a new
  policy; leave it empty to apply the policy to every company instead.
* **Conditions**: a domain built with Odoo's standard filter editor,
  evaluated against the vendor bill (``account.move``). An empty domain
  matches any vendor bill or vendor credit/debit note (a catch-all policy).
  A new policy's domain starts pre-filled with **Type is in Vendor Bill,
  Vendor Credit Note** and **Status = Draft** -- this module never actually
  evaluates a policy outside those conditions, so keeping them keeps the
  record count shown while editing the domain accurate; remove any of them
  if you really mean to build a domain that reads as broader. Any field of
  the bill can be used, e.g.:

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
  can never be confirmed nor approved by anyone, regardless of the
  Authorizers field (which is then ignored and hidden) and regardless of
  any other matching policy. Use this to explicitly and permanently deny a
  category of bills -- e.g. a policy with the condition "classification is
  not set" and Always block checked means vendor bills without a
  classification can never be confirmed.
* **Authorizers**: the users allowed to approve a bill matching this
  policy (ignored if Always block is checked). If a policy matches a bill
  but has no authorizers configured and Always block is not checked, that
  bill can also never be approved by anyone -- same practical effect as
  Always block, but it usually means the field was left empty by mistake
  rather than on purpose. Prefer checking Always block when that is the
  actual intent, so the policy documents itself.

If a bill matches more than one policy at the same time, it is enough for
the bill to be approved by **any** authorized user from **any** of the
matching (non-blocking) policies (the set of allowed approvers is the
union across all matching policies, not their intersection) -- unless at
least one of the matching policies has Always block checked, in which case
the bill can never be confirmed regardless of what the other matching
policies allow.

Policies are always evaluated against their current configuration when
someone tries to confirm, authorize, reject or unauthorize a bill, so
changing a policy takes effect immediately for every draft bill.

Usage
=====

Loading and confirming a vendor bill
------------------------------------

Load the vendor bill (or vendor credit/debit note) as usual. As soon as a
draft bill matches a policy, its **Authorization status** (in the new
**Authorization** tab, next to *Other Info*) shows *To authorize*, and the
tab lists the matching policies and the users who can authorize it -- it
does not wait for someone to first try **Confirm** and be blocked.

When someone clicks **Confirm**:

* If the bill does not match any policy, it is confirmed immediately,
  exactly as before this module was installed.
* If the bill was already authorized (see below), it is confirmed,
  whoever clicks **Confirm** -- it does not need to be an authorizer.
* If the user confirming is themselves an authorizer of a matching policy,
  the bill is authorized and confirmed in the same step.
* Otherwise the bill is **not** confirmed. Instead:

  * Its **Authorization status** stays *To authorize*.
  * An activity is assigned to every authorizer of every matching policy,
    so it shows up in their **My Activities** and triggers an email
    according to their own notification preferences.
  * A message is logged on the bill's chatter noting from whom
    authorization was requested.
  * The user gets an error message explaining that the bill is pending
    authorization.

* If the bill matches a policy with **Always block**, it is never
  confirmed, not even by an authorizer: the error message names the
  blocking policy so the data can be fixed.

These checks also apply to every other way of posting a bill (the *Post
entries* action on the list, auto-posting of future-dated bills, etc.):
a bill that is blocked or still awaiting authorization is never posted
from there either. The only exception is the credit note generated by a
full reversal (*Reverse* with *Full refund and new draft*) of a bill that
was already confirmed: it cancels a bill that already went through
authorization, so it is posted right away.

Authorizing or rejecting a pending bill
---------------------------------------

Open the bill. If you are one of the users authorized to act on it, the
header shows **Authorize + Confirm**, **Authorize** and **Reject**
instead of the regular **Confirm** button, so that authorizing is always
an explicit choice.

* **Authorize**: does *not* confirm the bill. It only sets the
  **Authorization status** to *Authorized* and the **Authorized by**
  field to you, marks the pending activities as done, and logs it on the
  chatter. The bill stays in *Draft*. Once authorized, **anyone** with the
  normal permission to confirm bills can click the regular **Confirm**
  button -- this lets the person who signs off on a bill be different from
  the person who actually confirms it.
* **Authorize + Confirm**: authorizes and confirms the bill in a single
  click, for when you are already reviewing it and there is no reason to
  leave it for someone else to confirm.
* **Reject**: opens a small window asking for a reason. Once confirmed,
  the bill's **Authorization status** becomes *Rejected*, the reason is
  stored on the bill and shown in the **Authorization** tab, the pending
  activities are marked done, and an activity is created for the user who
  loaded the bill, informing them of the rejection and the reason.
  Fixing the bill (see below) or trying to confirm it again requests
  authorization again.
* **Unauthorize**: authorized by mistake? While the bill is still a draft,
  an **Unauthorize** button appears next to **Confirm** for any user who is
  currently an authorizer of the bill (not only the one who authorized
  it). It reverts the **Authorization status** back to *To authorize*,
  clears **Authorized by**, logs it on the chatter, and notifies the user
  who loaded the bill. Once the bill is confirmed, it no longer applies.

Only users who are actually listed as authorizers on a matching policy can
authorize, reject or unauthorize a bill -- this is enforced on the server,
not just by hiding the buttons. Every authorization event (who authorized,
who confirmed, who rejected and why) is logged on the bill's chatter.

When an authorization is lost
-----------------------------

* Editing an already-authorized (or rejected) draft bill in a way that
  could change which policies match -- vendor, journal, currency, invoice
  or accounting date, classification, fiscal position, payment terms, or
  any of its lines (and therefore its amount) -- throws away that
  decision: its **Authorization status** goes back to *To authorize* (or
  *Not required*, if no policy matches anymore), **Authorized by** is
  cleared, and this is logged on the chatter. A bill can't be authorized
  for one amount and then confirmed after being changed to a different
  one. Editing other fields (e.g. the bill reference) keeps the
  authorization.
* Resetting an authorized, confirmed bill back to draft also throws away
  its authorization: it must be authorized again before it can be
  confirmed again.

Finding pending bills
---------------------

The **Bills** and **Refunds** lists (Accounting ‣ Vendors) offer extra
filters in the search bar:

* **To authorize**: draft bills currently waiting for an authorization
  that someone can actually give.
* **To authorize by me**: draft bills you are personally allowed to
  authorize or reject right now.
* **Authorized, not confirmed by me yet**: bills you loaded yourself that
  needed authorization, already got it, and are still sitting as a draft
  waiting to be confirmed.

The **Authorization status** column is also available in both lists
(hidden by default; enable it from the column selector).

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
