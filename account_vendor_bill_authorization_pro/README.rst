==================================================================
Autorización de facturas de proveedor - Excepción por pago directo
==================================================================

Some vendor bills are already paid when they are loaded -- typically from a
petty cash (*Fondo Fijo*) journal. Requiring an authorization (see
*Autorización de facturas de proveedor*, ``account_vendor_bill_authorization``)
for something that is already paid makes no operational sense.

This module builds on the **Pay now journal** (*Diario de pago directo*,
field ``pay_now_journal_id``) of ingadhoc's *Account Payment Super Power*
(``account_payment_pro``): a journal chosen on a draft vendor bill, which
automatically creates, posts and reconciles a payment from that journal as
soon as the bill is confirmed.

When the company configures **journals that bypass authorization** and the
**users allowed to use this bypass**:

* On vendor bills and vendor credit/debit notes, the *Pay now journal*
  selector only offers those journals, and only those users can set it.
* A bill whose pay now journal is one of those journals **does not require
  authorization**: no authorization policy is applied, its authorization
  status is *Not required*, and it can be confirmed directly.
* **Always block wins over the bypass.** If a policy marked *Always block*
  matches the bill, it stays blocked whatever its pay now journal.
* Only an allowed user can confirm a bill that has a pay now journal. Any
  other user gets an error, and the bill stays in draft.
* The payment created on confirmation also **skips vendor payment
  authorization** (*Autorización de pagos a proveedores*,
  ``account_payment_authorization``): the bill and its payment are
  confirmed together. Only a payment from a bypass journal that settles
  bills whose pay now journal is that same journal gets this. Payment
  policies marked *Always block* still block it.
* When a bill is confirmed through the bypass, a message in its chatter
  records which journal bypassed the authorization.

A bill without a pay now journal follows the normal authorization flow,
unchanged.

The whole module is inactive while the *Allow pay now on vendor invoices?*
setting is unchecked, or while no journal that bypasses authorization is
configured.

This module was built for a specific client's setup. It depends on
``account_payment_authorization``, as well as on ``account_payment_pro``
and ``account_journal_security`` (ingadhoc).

**Table of contents**

.. contents::
   :local:

Configuration
=============

#. Go to **Accounting ‣ Configuration ‣ Settings**, section **Vendor
   Payments**, and check **Allow pay now on vendor invoices?** (*Permitir
   pago directo en facturas de proveedores?*, from ``account_payment_pro``).
   The settings of this module only show up once it is checked.
#. In the **Vendor bill authorization bypass** setting just below it, set
   (per company):

   * **Journals that bypass authorization**: the petty cash (or similar)
     journals bills may be paid with when they are loaded. They need a
     *Manual* outgoing payment method, as the *Pay now journal* requires.
   * **Users allowed to use this bypass**: the only users who can set a pay
     now journal on a vendor bill, or confirm a bill that has one.

   Leaving the journals empty disables the bypass: the *Pay now journal*
   then works exactly as ``account_payment_pro`` defines it, for every
   user.
#. **Journal Security** (``account_journal_security``): restrictions set on
   each journal (*Advanced Settings ‣ Restrict to users*) keep applying on
   top of this module. A user restricted out of a journal (*Total*) can't
   see or pick it; a user without modification rights on it
   (*Modification*) can pick it, but confirming the bill fails, because
   the payment can't be created in that journal. Make sure the allowed
   users above also have rights on the bypass journals in Journal Security.
#. **Vendor payment authorization** (``account_payment_authorization``):
   no extra setup is needed. Payment policies don't apply to the payment
   created when a bypassed bill is confirmed, except policies marked
   *Always block*. A payment policy marked *Always block* that matches
   that payment (e.g. one conditioned on the petty cash journal) leaves
   the bill confirmed and its payment blocked in draft, so avoid such
   policies on the bypass journals. Every other payment goes through
   payment authorization as usual: payments from other journals, and
   payments from a bypass journal that settle something other than bills
   with that same pay now journal.

Usage
=====

#. As an allowed user, create a vendor bill (or vendor credit/debit note)
   as usual.
#. In **Pay now journal**, pick the petty cash journal the bill was paid
   with. Only the journals that bypass authorization are offered. The
   **Authorization** status changes to *Not required*, unless an *Always
   block* policy matches the bill.
#. Click **Confirm**. The bill is confirmed, a payment from that journal is
   created, posted and reconciled with it, and the chatter records that
   the authorization was bypassed and with which journal.

Notes:

* Users who are not allowed to use the bypass see the *Pay now journal*
  as read-only, and can't confirm a bill that has one (they get an error).
  They can still load bills without a pay now journal, which go through
  the normal authorization flow.
* Choosing the pay now journal on a bill that was already authorized or
  rejected discards that decision: the bill no longer requires
  authorization.
* Clearing the pay now journal puts the bill back into the normal
  authorization flow.

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
