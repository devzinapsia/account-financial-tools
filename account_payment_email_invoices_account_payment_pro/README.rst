===================================================================
Facturas adjuntas al enviar órdenes de pago y recibos - Payment Pro
===================================================================

Glue between *Facturas adjuntas al enviar órdenes de pago y recibos*
(``account_payment_email_invoices``) and ingadhoc's *Account Payment Super
Power* (``account_payment_pro``). Installed automatically when both are.

With ``account_payment_pro``, a **payment bundle** (``l10n_ar_payment_bundle``)
is a main payment without journal entry of its own, plus linked payments
(one per payment method) that settle the debts. When the main payment is
sent by email, this module attaches the documents settled by its linked
payments, including the credit notes applied within the bundle.

Payments of ``account_payment_pro`` that are not bundles already work with
the base module: it detects the credit notes applied within the payment
order or receipt (reconciled with an invoice in the same operation), and a
partial payment only attaches the debts it actually reached, not every debt
selected in it.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Nothing to configure: the settings are the ones of
*Facturas adjuntas al enviar órdenes de pago y recibos*, in **Accounting ‣
Configuration ‣ Settings**, section **Payment emails**.

Usage
=====

Send the main payment of a payment bundle by email as any other payment
order or receipt: its email carries the documents settled by the linked
payments of the bundle.

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
