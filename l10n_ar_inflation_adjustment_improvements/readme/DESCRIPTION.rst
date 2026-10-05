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
