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
  first-notice value, and the first notice has not been sent yet, it
  sends the first notice.
* If a second notice is enabled and the number of days left matches the
  configured second-notice value, and the second notice has not been
  sent yet, it sends the second notice.

Both checks are independent, so a document can receive both notices in
separate runs, or even on the same day if the two configured values
coincide. Each notice is sent once per document: sending it stamps the
document with the date and time it was sent, so it is never sent twice.
A document that gets reconciled or paid before its turn comes up simply
stops matching the criteria above, so no further notices go out for it.

All documents due on the same run for the same notice are sent as a
**single email**, not one email per document -- if five bills are due
in 3 days, that is one email listing all five, not five separate ones.
Its subject is **"Vencimientos a pagar hoy"** when the notice is for the
same day, or **"Vencimientos a pagar en ## días"** otherwise, where
``##`` is the configured number of days. The body lists, for every
document in that batch, its type and number (with a link to it), the
vendor, the reference, the due date, and the amount due; if any
**Accounts to report balance** are configured, their current balance is
added at the foot of the email.

Each notice is sent through the standard Odoo notification system, so
every configured user gets it by email or as an internal notification
according to their own preference (**Settings ‣ Preferences ‣
Notification**).

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
