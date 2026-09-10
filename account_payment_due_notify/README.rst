=======================================
Notificaciones de vencimientos de pago
=======================================

Replaces a manual process of assigning an activity to each payable
document and running a scheduled action to notify by email or chat: this
module automates the whole cycle.

It watches every posted, unreconciled journal item with a payable account
(``account_type = liability_payable``), a vendor contact, and a due date
-- vendor bills, vendor credit notes, and manual entries (e.g. VAT
payable) alike, whether or not they use fiscal documents. Before each
such item's due date, it notifies a configured list of users, respecting
each user's own notification preference (email or internal notification),
exactly like the manual process it replaces.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Settings**, in the **Vendor
Payments** section, under **Payment due notifications**:

* **Notify on payment due dates**: master switch for this company. All
  other fields below only show once this is checked.
* **Days before due date (first notice)**: how many days before a
  document's due date the first notice is sent. 0 means the same day it
  is due. Default: 3.
* **Send a second notice**: optional second notice. If unchecked, only
  the first notice above is ever sent, and the days field below is not
  evaluated at all. Default: checked.
* **Days before due date (second notice)**: how many days before the due
  date the second notice is sent, only used if **Send a second notice**
  is checked. 0 means the same day it is due. Default: 0.
* **Send a weekly payment due summary (Mondays)**: optional. Every
  Monday, in addition to any first/second notice due that day, sends a
  separate digest listing every payable document due that same Monday
  through the following Sunday, sorted by due date. Default: unchecked.
* **Notification time**: approximate local time of day, in the timezone
  below, at which notices are sent. The check that sends notices runs
  every 30 minutes, so the actual send time can be up to 30 minutes
  after this.
* **Notification timezone**: timezone used to evaluate the time above.
  Suggested automatically from the company's country when every zone in
  that country currently shares the same UTC offset (e.g. Argentina);
  left empty otherwise (e.g. the US, Brazil) -- it is never assumed from
  the server, so set it explicitly if it is not suggested.
* **Users to notify**: the users who receive notices, restricted to
  internal users (portal/public users are not offered). This list is
  global per company; it does not vary by vendor or journal.
* **Accounts to report balance**: optional accounts, restricted to
  active accounts of type Bank and Cash, whose current balance is added
  at the foot of every notification email, as a quick reference for
  whether there are enough funds to pay. Leave empty to not include any
  balance information. This is only a reference: it does not account
  for pending collections, other scheduled payments, or checks in
  transit -- it is most useful when a notice is for "today".

Usage
=====

Once enabled, this module works entirely on its own -- there is nothing
to trigger by hand.

Every 30 minutes, for each company with the feature enabled, it checks
whether the current time (in that company's configured timezone) falls
in the same 30-minute window as the configured notification time. When
it does, it looks at every posted, unreconciled payable journal item with
a vendor and a due date, and for each one:

* If the number of days left until the due date matches the configured
  first-notice value, it sends the first notice.
* If a second notice is enabled and the number of days left matches the
  configured second-notice value, it sends the second notice.

Both checks are independent, so a document can receive both notices in
the same run if the two configured values coincide. There is no
per-document "already notified" tracking: each run simply sends
whatever currently matches, in full, as if it were the first time. In
practice this means each notice normally goes out once, since a
document's days-left count only equals a given configured value on one
specific day -- but if the notification time is reconfigured mid-day,
or the check is triggered by hand more than once, the same set is sent
again rather than being silently skipped; there is nothing to get stuck
if a due date is corrected later, either (reset to draft, fix the date,
post again -- the next run picks it up under the new date with no
extra step). A document that gets reconciled or paid before its turn
comes up simply stops matching the criteria above.

All documents due on the same run for the same notice are sent as a
**single email**, not one email per document -- if five bills are due
in 3 days, that is one email listing all five, not five separate ones.

Its subject is **"Vencimientos a pagar hoy (##/##/####) en <company>"**
when the notice is for the same day, or **"Vencimientos a pagar en ##
días (##/##/####) en <company>"** otherwise, where the first ``##`` is
the configured number of days, ``(##/##/####)`` the actual due date of
every document in that batch, and ``<company>`` this company's name.
The body starts with a bold **"Comprobantes a pagar:"** line (the date
is already in the subject, so it is not repeated here), then a table
with, for every document in that batch, the vendor, its type and number
(with a small external-link icon to it), the reference, and the amount
due, right-aligned; if any **Accounts to report balance** are
configured, their current balance (name only, no account code) is added
at the foot of the email under a bold **"Saldo de bancos y efectivo"**
heading, also right-aligned.

If **Send a weekly payment due summary (Mondays)** is checked, every
Monday -- in the same notification window as the daily notices above --
a separate digest is sent listing every payable document due that same
Monday through the following Sunday, sorted ascending by due date (with
the due date as its own first column, since unlike the daily digest a
week can span several different dates). Its subject is
**"Vencimientos a pagar esta semana (##-##-#### a ##-##-####) en
<company>"**. Unlike the daily notices, it does track (per company)
the last Monday it was sent for, so it only goes out once per Monday
even if the check runs more than once in that day's window.

Each notice is sent through the standard Odoo notification system, so
every configured user gets it by email or as an internal notification
according to their own preference (**Settings ‣ Preferences ‣
Notification**). No mail signature is appended.

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
