================================
Mejoras al ajuste por inflación
================================

This module improves the "Asiento de ajuste por inflación" (inflation
adjustment entry) wizard added by Adhoc's ``l10n_ar_account_reports``
(**Accounting ‣ Accounting ‣ Asiento de ajuste por inflación**).

Upstream, when the user answers *Yes* to "Has closing/opening entries?"
(*¿Ha realizado asientos de cierre/apertura?*), the wizard asks for exactly
one closing entry and one opening entry to exclude from the calculation.
That doesn't work when the closing/opening was split into several entries,
or when a dedicated journal holds them all.

New question
============

When the first question is answered *Yes*, a second one is shown:
"Specify individual entries?" (*¿Indica los asientos individuales?*):

* **Yes** (default): same behavior as upstream. The closing entry and the
  opening entry are required, shown right below the new question, and
  only those 2 entries are excluded.
* **No**: those 2 fields are hidden and a new "Journal where they are
  posted" (*Diario en el que están registrados*) field is required
  instead, limited to miscellaneous journals of the wizard's company.
  **Every** posted entry of that journal is excluded from the adjustment,
  both from the initial balance and from each monthly period.

If the first question is answered *No*, none of these fields are shown or
required, and nothing is excluded (upstream behavior).

The selected journal can't be the same journal where the adjustment entry
is created, since that would also exclude previous inflation adjustment
entries. Both rules are enforced in Python too, not only in the form.

Translation fix
===============

The wizard's "Journal" field had no Spanish translation upstream. It is
now translated as *Diario*.

Technical note
==============

Upstream builds the move line domain used for both the initial balance
and every period in a single method, ``get_move_line_domain()``. This
module extends that method with ``super()`` to add the journal exclusion,
so ``confirm()`` itself isn't duplicated. Fields hidden by the current
answers are cleared, both by an onchange and right before ``confirm()``,
so a stale closing/opening entry can't be excluded by mistake.

**Table of contents**

.. contents::
   :local:

Configuration
=============

No configuration is needed. If you want to exclude a whole journal, make
sure the closing/opening entries are posted in a miscellaneous journal
used only for them, different from the journal where the inflation
adjustment entry is created.

Usage
=====

#. Go to **Accounting ‣ Accounting ‣ Asiento de ajuste por inflación**.
#. Answer *Yes* to "Has closing/opening entries?".
#. Answer "Specify individual entries?":

   * *Yes*: select the closing entry and the opening entry.
   * *No*: select the journal where the closing/opening entries are
     posted. All its entries will be left out of the adjustment.

#. Click **Confirm**.

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
