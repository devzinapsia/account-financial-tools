===================================================
 Mejoras a traducciones contables - Pagos en línea
===================================================

Glue module between ``account_translation_improvements`` and
``account_payment``, installed automatically when both are installed.

``account_payment`` hides the invoice form's "Pay" buttons while the
invoice has an authorized online transaction that hasn't been captured or
voided yet, so a manual payment can't be registered on top of it.
``account_translation_improvements`` shows a "Collect" button instead of
"Pay" on customer documents; this module applies that same rule to the
"Collect" buttons.

It's a separate module so that ``account_translation_improvements`` only
depends on ``account``.

**Table of contents**

.. contents::
   :local:

Configuration
=============

No configuration is needed.

Usage
=====

No user action is needed. On a customer invoice with an authorized
transaction, capture or void it first; the **Cobrar** button shows up
again afterwards, just like **Pagar** does on the vendor side.

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
