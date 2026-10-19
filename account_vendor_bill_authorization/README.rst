=====================================
Autorización de facturas de proveedor
=====================================

Some users load and confirm vendor bills, but certain bills should not be
paid without another user's approval first -- for example, bills above a
given amount, bills from a sensitive vendor, or bills with a particular
classification.

This module adds configurable **vendor bill authorization policies**. Each
policy defines a set of conditions on the bill (any field: classification,
vendor, journal, amount...) and a list of users allowed to authorize a bill
matching those conditions. A bill matching at least one policy can be
confirmed as usual, but it **can't be paid** until one of those users has
authorized it. A policy can also be marked **Always block**, so that
matching bills can never be confirmed at all.

The flow has three separable steps:

#. Whoever loads the bill confirms it. If it matches a policy, it is left
   *To authorize* and the authorizers are notified.
#. An authorizer reviews it and **authorizes** it, or **rejects** it with
   a reason.
#. Once authorized, whoever is in charge of payments **pays** it, as
   usual.

**Scope: vendor bills and vendor credit/debit notes only** (journal entries
of type *Vendor Bill* / *Vendor Credit Note*, i.e. ``in_invoice`` and
``in_refund``; vendor debit notes are ``in_invoice`` bills). Customer
invoices and credit notes, purchase receipts, and miscellaneous journal
entries are never affected, whatever the policies say.

This module is independent from *Autorización de pagos a proveedores*
(``account_payment_authorization``), which applies a similar pattern to
vendor payments: either one can be installed without the other. When
ingadhoc's ``account_payment_pro`` is installed, the bridge module
*Autorización de facturas de proveedor - Payment Pro* installs
automatically and applies the same rules to its payment receipts.

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

Usage
=====

Confirming a vendor bill
------------------------

Load and confirm the vendor bill (or vendor credit/debit note) as usual.
Anyone allowed to confirm bills can do it.

* If the bill does not match any policy, nothing changes: it can be paid
  right away, exactly as before this module was installed.
* If the bill matches a policy with **Always block**, it can't be
  confirmed, by anyone: the error message names the blocking policy so the
  data can be fixed.
* If the bill matches any other policy, it is confirmed, and:

  * Its **Authorization status** (in the **Authorization** tab, next to
    *Other Info*) becomes *To authorize*; the tab also lists the matching
    policies and the users who can authorize it.
  * An activity is assigned to every authorizer of every matching policy,
    so it shows up in their **My Activities** and triggers an email
    according to their own notification preferences.
  * A message is logged on the bill's chatter noting from whom
    authorization was requested.
  * The bill **can't be paid** until it is authorized (see below).

Confirming a bill does not authorize it, not even when the user
confirming it is an authorizer: authorizing is always an explicit step.

These rules apply to every way of confirming a bill (the *Confirm* button,
the *Post entries* action on the list, auto-posting of future-dated
bills, etc.).

Authorizing or rejecting a confirmed bill
-----------------------------------------

Open the bill. If you are one of the users authorized to act on it, the
header shows **Authorize** and **Reject**.

* **Authorize**: sets the **Authorization status** to *Authorized* and the
  **Authorized by** field to you, removes the pending authorization
  requests, and logs it on the chatter. From then on, **anyone** with the
  normal permission to pay bills can pay it: the person who signs off on a
  bill can be different from the person who actually pays it.
* **Reject**: opens a small window asking for a reason. Once confirmed,
  the bill's **Authorization status** becomes *Rejected*, the reason is
  stored on the bill and shown in the **Authorization** tab, the pending
  authorization requests are removed, and an activity is created for the
  user who loaded the bill, informing them of the rejection and the
  reason. A rejected bill can't be paid. To fix it, reset it to draft,
  edit it and confirm it again (authorization is then requested again),
  or cancel it with a credit note.
* **Unauthorize**: authorized by mistake? While the bill has no payment
  yet, an **Unauthorize** button appears for any user who is currently an
  authorizer of the bill (not only the one who authorized it). It reverts
  the **Authorization status** back to *To authorize*, clears
  **Authorized by**, logs it on the chatter, and notifies the user who
  loaded the bill.

Only users who are actually listed as authorizers on a matching policy can
authorize, reject or unauthorize a bill -- this is enforced on the server,
not just by hiding the buttons. Every authorization event (who authorized,
who rejected and why) is logged on the bill's chatter.

The authorization requests are removed (without cluttering the chatter)
as soon as nobody needs to act on them anymore: when the bill is
authorized, rejected, reset to draft, cancelled, or stops matching any
policy.

Paying
------

While a bill is *To authorize* or *Rejected*:

* the **Pay** button is hidden, and refused if called anyway (e.g. from
  the list's *Pay* action, with several bills selected);
* the *Register Payment* wizard refuses to create the payment;
* it can't be reconciled in any other way either: matching it with a
  payment by hand or from the bank reconciliation, or applying an
  outstanding credit or a credit note to it from the bill;
* with ingadhoc's ``account_payment_pro``, payment receipts leave it out
  of the vendor's debt they fill in, refuse it if it is added by hand, and
  a bill that requires authorization can't be confirmed with a **pay
  now** journal (it would be paid before being authorized): remove the pay
  now journal, confirm it, and pay it once authorized.

The only exception is the credit note generated by a full reversal
(*Reverse* with *Full refund and new draft*): it cancels the bill rather
than paying it.

When an authorization is lost
------------------------------

* Editing an authorized (or rejected) bill in a way that could change
  which policies match -- vendor, journal, currency, invoice or accounting
  date, classification, fiscal position, payment terms, or any of its
  lines (and therefore its amount) -- throws away that decision: its
  **Authorization status** goes back to *To authorize* (or *Not required*,
  if no policy matches anymore), **Authorized by** is cleared, the
  authorizers are asked again, and this is logged on the chatter. Editing
  other fields (e.g. the bill reference) keeps the authorization.
* Resetting a confirmed bill back to draft throws away its authorization
  status: it is evaluated again, from scratch, when it is confirmed again.

Finding pending bills
---------------------

The **Bills** and **Refunds** lists (Accounting ‣ Vendors) offer extra
filters in the search bar:

* **To authorize**: confirmed bills currently waiting for an authorization
  that someone can actually give.
* **To authorize by me**: confirmed bills you are personally allowed to
  authorize or reject right now.
* **Authorized, pending payment**: authorized bills that still haven't
  been (fully) paid.

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
