===================================================
Account Payment Authorization - Payment Pro
===================================================

``account_payment_authorization`` decides whether a vendor payment needs
authorization based on conditions that can reference the vendor bill it is
meant to pay, through the payment's ``invoice_ids`` field.

That field is normally populated by ``account_payment_authorization``
itself when a payment is created through the standard "Register Payment"
wizard. ``account_payment_pro`` (ingadhoc) replaces that wizard entirely
with a different flow: the payment is drafted directly, and the debt it
settles is tracked via ``to_pay_move_line_ids`` instead, well before the
payment is confirmed.

This bridge module keeps both flows working the same way: it mirrors the
vendor bill from ``to_pay_move_line_ids`` into ``invoice_ids`` whenever
``account_payment_pro`` is the one driving payment creation, so
authorization scheme conditions referencing ``invoice_ids`` (e.g.
``invoice_ids.classification_id``) match correctly regardless of which
module created the payment.

It has no configuration of its own and installs automatically once both
``account_payment_authorization`` and ``account_payment_pro`` are present.

**Table of contents**

.. contents::
   :local:

Configuration
=============

No configuration is required. It auto-installs once both
``account_payment_authorization`` and ``account_payment_pro`` are
installed.

Usage
=====

Nothing to do -- configure payment authorization schemes as documented in
``account_payment_authorization``. Draft a vendor payment through
``account_payment_pro``'s own flow (selecting debt lines via "To Pay
Lines") and the scheme conditions will see the linked bill exactly as if
the payment had been registered through the standard wizard.

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
