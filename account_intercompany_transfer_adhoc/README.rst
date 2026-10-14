===================================================
Transferencias intercompany - Banco y Caja de adhoc
===================================================

Glue module between ``account_intercompany_transfer`` and ingadhoc's
``account_internal_transfer``. It installs automatically when both are
installed.

It moves the **Intercompany transfers** menu to **Accounting ‣ Bank and
Cash**, right below ingadhoc's **Transfers**, so both kinds of transfers sit
next to each other. Without ingadhoc's module, the entry stays in
**Accounting ‣ Accounting ‣ Transactions**.

Only the menu changes. Intercompany transfers and ingadhoc's internal
transfers stay fully apart, in both directions, through
``account_intercompany_transfer``'s own marker: its payments carry none of
the fields ingadhoc uses to recognize an internal transfer, so they never
show up in ingadhoc's *Transfers* list, filters or report, and ingadhoc's
payments can never be linked to an intercompany transfer. This was checked
with both modules installed, so this module doesn't change any of
ingadhoc's domains or filters.

When this module is uninstalled (on its own, or because ingadhoc's module
is), the menu goes back to **Accounting ‣ Accounting ‣ Transactions**.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Nothing to configure: it installs automatically when
``account_intercompany_transfer`` and ``account_internal_transfer`` are both
installed. See ``account_intercompany_transfer`` for the bridge accounts and
access rights.

Usage
=====

Go to **Accounting ‣ Bank and Cash ‣ Intercompany transfers**. The menu is
only visible to users with the *Intercompany transfers / User* access right
who also see ingadhoc's **Bank and Cash** menu.

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
