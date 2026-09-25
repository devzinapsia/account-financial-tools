====================================================
 Mejoras a traducciones contables - Pagos por lotes
====================================================

Glue module between ``account_translation_improvements`` and Odoo
Enterprise's ``account_batch_payment``, installed automatically when both
are installed.

It applies the same wording change as ``account_translation_improvements``
to the customer side of batch payments:

* **Customers ‣ Batch Payments** menu: renamed to "Batch Collections"
  ("Cobros por lotes").
* Its window title ("Customer Batch Payments"): renamed to "Batch
  Collections" ("Cobros por lotes") too.

The vendor side (**Vendors ‣ Batch Payments**) is left untouched.

Technical notes
===============

* Both records belong to ``account_batch_payment``. Their Spanish texts are
  written with ``update_field_translations()`` from this module's own po
  files on every install/upgrade, because a regular translation load never
  replaces the translation ``account_batch_payment`` already set on them.
* Uninstalling the module restores the original names ("Batch Payments",
  "Customer Batch Payments") and their translations from
  ``account_batch_payment``'s po files.

**Table of contents**

.. contents::
   :local:

Configuration
=============

No configuration is needed.

Usage
=====

Go to **Facturación ‣ Clientes**: the batch payments menu reads **Cobros
por lotes**, and so does the title of the screen it opens.

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
