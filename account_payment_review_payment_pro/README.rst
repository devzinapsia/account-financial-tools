=========================================
Revisión de órdenes de pago - Payment Pro
=========================================

Glue between account_payment_review and ingadhoc's account_payment_pro.
Installs automatically when both are installed.

Under account_payment_pro the amount that matters for a payment order is
its total (``payment_total``): the payment itself plus write-off and,
with l10n_ar_tax, withholdings. This module makes the **Review from
amount** setting compare against that total, converted to company
currency, instead of the payment's own amount. It also shows that total
in the review wizard.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Nothing to configure: the **Review from amount** setting of
account_payment_review now applies to the payment order's total.

Usage
=====

Use account_payment_review as usual. A payment order whose total
(including withholdings) is below **Review from amount** starts as *Not
required* when confirmed.

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
