=====================================
Account Account Previous System Code
=====================================

When migrating a customer's chart of accounts from their previous system,
it is useful to keep track of the account code each account had in that
system, so it can be referenced later (mappings, reconciliations,
historical lookups, etc.).

This module adds a "Previous system account code" field to
``account.account``, searchable and available as an optional column in
the chart of accounts list. The code is free-form and optional, but when
set it must be unique among accounts sharing a company (directly, or
through a parent/child company relationship).

**Table of contents**

.. contents::
   :local:

Configuration
=============

No configuration is required. Once installed, the new field is available
on every account.

Usage
=====

Go to **Accounting ‣ Configuration ‣ Chart of Accounts**, open an account,
and fill in the **Previous system account code** field next to the
account's **Code**.

The column is available in the chart of accounts list (hidden by default;
enable it from the column selector) and the field can be used from the
search bar to look up an account by its previous system code.

If you try to save two accounts sharing a company with the same previous
system account code, Odoo raises a validation error. Leaving the field
empty is always allowed, even on multiple accounts at once.

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
