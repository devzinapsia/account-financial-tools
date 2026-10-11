===========================
Revisión de órdenes de pago
===========================

Internal control over vendor payments **after** they are confirmed. A
reviewer (typically one of the company's partners) goes through confirmed
vendor payments -- usually in batches, e.g. at month end -- and either signs
each one off as reviewed or records observations on it. The user who issued
the payment is notified of the observations, answers them, and the payment
goes back to the reviewer.

The review is a parallel control layer: it never blocks, resets or
modifies the payment itself, its journal entry or its reconciliation. It
only adds a review status, who reviewed it and when, the comments, and a
signed message in the chatter.

Review statuses:

* **Pending review**: confirmed after the circuit was enabled, waiting for
  the reviewer.
* **Reviewed**: signed off by the reviewer.
* **With observations**: the reviewer left a comment the issuer must
  answer.
* **Answered**: the issuer answered the observations; back to the
  reviewer.
* **Not required**: confirmed before the module was installed, matching an
  exemption, or explicitly marked so by the reviewer.

Customer payments are not part of the circuit.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Reviewers
---------

Pick them in **Accounting ‣ Configuration ‣ Settings ‣ Vendor Payments ‣
Payment review ‣ Payment reviewers**, or, equivalently, open each user in
**Settings ‣ Users & Companies ‣ Users** and, under **Accounting**, set
**Payment review** to *Payment reviewer*. Both edit the same access right,
which applies to every company. A reviewer only needs read access to
accounting: the group implies the read-only accounting profile, and
reviewing never requires rights to modify payments.

Review settings
---------------

Go to **Accounting ‣ Configuration ‣ Settings ‣ Vendor Payments ‣ Payment
review** (per company):

* **Payment review**: enables the circuit. Vendor payments confirmed from
  then on start as *Pending review*, unless an exemption applies.
* **Review from amount**: vendor payments below this amount, in company
  currency, start as *Not required*. Leave it at 0 to review payments of
  any amount.
* **Payments that don't require review**: conditions built with Odoo's
  filter editor, e.g. *Journal = Petty cash* or a given vendor. Matching
  payments start as *Not required*. Leave it empty for no exemption.
* **Days to answer observations**: deadline of the activity assigned to
  the issuer when the reviewer records observations (3 by default).

Exemptions are evaluated once, when a payment is confirmed: changing them
does not reclassify payments already confirmed. A reviewer can still
review any *Not required* payment on purpose, or mark pending ones as
*Not required* from the review wizard.

Vendor payments confirmed before the module was installed start as *Not
required*, so the circuit applies from the installation onwards.

Usage
=====

Reviewing (reviewer)
--------------------

Go to **Accounting ‣ Vendors ‣ Payments to review**. It opens the
confirmed vendor payments filtered by *Pending review* and *Answered*; use
the standard filters and group-bys (date, journal, payment method, vendor,
amount) to pick which ones to review.

* **One payment**: open it and click **Review**. Choose *OK*, *With
  observations* (comment required) or *Not required*, plus an optional
  comment.
* **Several payments**: select them in the list and use **Actions ‣
  Review**. The wizard shows one line per payment, all set to *OK* by
  default; change the result and add a comment per line where needed
  (required for *With observations*). Remove a line to leave a payment
  out.

Every decision is posted in the payment's chatter as an internal message
authored by the reviewer (the reviewer's "signature"): who, when, the
result and the comment. Review messages are internal and never e-mailed
to the payment's followers.

The reviewer can change their mind at any time, e.g. turn a *Reviewed*
payment into *With observations* when something comes up at month end.

Answering observations (issuer)
-------------------------------

When the reviewer records observations, the user who confirmed the
payment gets a *Payment review observation* activity with the comment,
due in the configured number of days. Make whatever adjustment is needed
(this module never changes the payment) and click **Answer observations**
on the payment: the activity is closed, the answer is posted in the
chatter, the payment becomes *Answered* and the reviewer gets an activity
to review it again. Any accounting user can answer on the issuer's behalf.

The **My payments with observations** filter lists the issuer's own
payments still waiting for an answer.

Visibility
----------

* A colored badge next to the payment number in the payment lists:
  *Pending review* (blue), *Reviewed* (green), *With observations* (red),
  *Answered* (orange). *Not required* shows no badge.
* The same badge under the number on the payment form, and a **Review**
  tab with the reviewer, review date, issuer, comment and answer.
* Optional **Review status**, **Reviewer** and **Review date** columns in
  the vendor payments list, and **Review status** / **Reviewer** group-bys.
* The list's own **Journal** and **Payment method** columns tell which
  journal and payment method each payment used. With ingadhoc's payment
  bundles (pagos múltiples) they show the bundle's own journal and method
  instead of the actual ones: see the
  account_payment_review_payment_bundle module's README.

Permissions
-----------

* Only *Payment reviewers* can review or mark payments as not required,
  enforced on the server, not only by hiding buttons: review fields can't
  be changed through list editing, import or direct API calls either.
* A reviewer can't review a payment they created or confirmed themselves.
* Answering observations is open to the payment's issuer and to any user
  with the *Invoicing* accounting rights.

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
