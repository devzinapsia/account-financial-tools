====================================
Aviso de percepciones solo en ventas
====================================

The ``l10n_ar_tax`` module (Adhoc) shows a warning banner on the invoice
form when the fiscal position has perception taxes and the invoice date is
still empty, explaining that perceptions will be recomputed when the date
is set or the invoice is posted.

Perceptions are only added on sale documents, but fiscal positions are
auto-detected by contact (ARCA responsibility type), not by document type.
A Registered VAT supplier therefore gets the perceptions fiscal position on
its vendor bills too, and the banner shows up there, where it is easily
confused with the perceptions charged by the supplier.

This module keeps the banner only on customer invoices, customer credit
notes and sales receipts. Nothing else changes: the fiscal position is
still detected on vendor bills (it does not alter their taxes), and the
perception computation of ``l10n_ar_tax`` is untouched.

**Table of contents**

.. contents::
   :local:

Configuration
=============

No configuration is needed. Install the module.

Usage
=====

Create a vendor bill for a supplier whose detected fiscal position has
perception taxes: the warning banner is no longer shown. Customer invoices
and credit notes with that fiscal position keep showing it until the
invoice date is set.

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
