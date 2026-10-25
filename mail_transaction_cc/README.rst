==================================
Correos en copia en transacciones
==================================

Sends the emails of certain transactions with internal addresses in
**visible copy (Cc)** for the customer or vendor, plus an optional
**hidden copy (Bcc)**.

Odoo sends one individual email per recipient partner, so adding
partners or followers never produces a real "Cc" header. This module
puts the copies in the *same* email the customer or vendor receives:
``To: customer`` and ``Cc: internal addresses`` in the real email
header, and the Bcc addresses in the SMTP envelope only (never visible
in the headers).

Supported transactions:

* **Customer invoice**: customer invoices and credit notes (debit notes
  included).
* **Receipt**: customer payments, in any direction (customer refunds
  included). Internal transfers are excluded.
* **Payment order**: vendor payments, in any direction (vendor refunds
  included). Internal transfers are excluded.
* **Purchase**: requests for quotation and purchase orders. Available
  automatically as soon as Purchase is installed, without updating this
  module; this module does not depend on Purchase.

It only depends on ``account`` and ``mail``, and works with or without
Adhoc's receiptbooks installed (their automatic receipt email is a
document sending too).

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Accounting ‣ Email copies** (only
for *Accounting / Administrator* users) and create one rule per need:

* **Transaction type**: customer invoice, receipt, payment order or
  purchase (only types whose application is installed are offered).
* **Company**: the rule applies to documents of this company, whatever
  the company the sending user is working in.
* **Scope**:

  * *All communication* (default): document sending, messages sent to
    the customer or vendor from the record's chatter, and forwarding of
    incoming emails.
  * *Document sending only*: the sending wizards (single and batch),
    background sending, and automatic reminders of the document (e.g.
    the purchase receipt reminder).

* **Additional condition**: optional domain on the transaction (e.g. a
  journal or an amount). Leave it empty to apply the rule to every
  record of the type.
* **Visible copy (Cc)**: free emails (separated by commas or
  semicolons), users, groups (members resolved when the email is sent),
  and **Include the responsible** (salesperson of the invoice, creator
  of the payment, buyer of the purchase order).
* **Hidden copy (Bcc)**: free emails, users and groups.

A rule needs at least one recipient. When a document matches several
rules, all their addresses are merged.

Usage
=====

Nothing to do by hand: once a rule exists, the copies are added
automatically.

**Outgoing emails.** When a document is sent (invoice sending wizard,
receipt / purchase order email, background sending, reminders), or,
with the *All communication* scope, when a message is sent to the
customer or vendor from the chatter:

* the customer or vendor receives a single email with the rule's
  addresses in ``Cc``, and the ``Bcc`` addresses receive it without
  appearing anywhere;
* addresses already in ``To`` are removed from Cc / Bcc, and an address
  both in Cc and Bcc stays in Cc only;
* internal users in Cc / Bcc who also follow the record receive only
  that copy, not a second notification;
* the Cc addresses show in the message's delivery information (envelope
  icon) in the chatter; the Bcc addresses do not.

Copies are never added to internal notes, automatic messages (tracking,
status changes, payment registered), messages without an external
recipient, nor to messages of any other model (contacts, manual journal
entries...) even when they attach the transaction's PDF. An invoice
opened from *Accounting ‣ Journal Entries* is the same record, so it is
covered.

**Incoming emails** (*All communication* scope only). When an email
reaches the chatter of a transaction (a reply to its reply-to), it is
forwarded to the rule's Cc and Bcc addresses, whatever the sender.
Addresses that already received the original email are skipped, Bcc
addresses are never exposed (when there is no Cc, each Bcc address
receives its own email), and replying to the forward goes back to the
record's chatter.

Rules are resolved as superuser: users without access to the rules still
send with the copies. A rule with an invalid condition is ignored (and
logged) instead of blocking the sending; archived users or users without
an email are skipped and logged.

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
