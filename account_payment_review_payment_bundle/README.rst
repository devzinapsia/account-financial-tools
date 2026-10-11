=============================================
Revisión de órdenes de pago - Pagos múltiples
=============================================

Glue between account_payment_review and ingadhoc's l10n_ar_payment_bundle.
Installs automatically when both are installed.

A payment bundle is made of a **main payment** (the payment order the user
sees, with an amount of 0) and **linked payments**, one per payment method
(cash, check, transfer...). This module makes only the main payment
reviewable: linked payments stay out of the review circuit, its filters,
the *Payments to review* menu and the review wizard. Together with
account_payment_review_payment_pro, the **Review from amount** setting is
compared against the bundle's total.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Nothing to configure.

Usage
=====

Review the bundle's main payment as any other payment. Its linked
payments never show a review status.

What the payment lists show for a bundle
----------------------------------------

Only the main payment is listed (ingadhoc's *Main Payments* filter, and
the *Payments to review* menu, leave the linked payments out). On that
row:

* **Journal** and **Payment method** show the bundle's own ones
  (*Multiple payments* / *Payment multiple*), not the actual payment
  methods used (cash, checks, transfers...).
* **Amount** shows 0, since the main payment has no amount of its own;
  the **Payment total** column (added by account_payment_pro) shows the
  real total, which is also what the review wizard shows.

To see which payment methods a bundle used, open it and check its
**Payments** tab. This also means the standard *Journal* / *Payment
method* filters and group-bys don't find a bundle by the payment methods
it was paid with, e.g. "payment orders paid with checks".

Payments made with a single payment method (no bundle) show their real
journal and payment method as usual.

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
