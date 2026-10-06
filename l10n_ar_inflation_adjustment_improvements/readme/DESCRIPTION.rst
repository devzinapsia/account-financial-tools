This module improves the "Asiento de ajuste por inflación" (inflation
adjustment entry) wizard added by Adhoc's ``l10n_ar_account_reports``
(**Accounting ‣ Accounting ‣ Asiento de ajuste por inflación**).

Upstream, when the user answers *Yes* to "Has closing/opening entries?"
(*¿Ha realizado asientos de cierre/apertura?*), the wizard asks for exactly
one closing entry and one opening entry, and excludes both from the
calculation. That works for a regular fiscal year, but not:

* when the opening was split into several entries (e.g. extra opening
  entries correcting the first one, because some of its lines were
  already reconciled with bank statements and it can't be reset to draft
  without losing them), or
* on the first fiscal year recorded in Odoo, which has an opening entry
  but no closing one. Answering *No* adjusts the opening entry as a
  movement of its month, one month short of inflation on every opening
  balance; indicating a hand-made reverse closing entry leaves the opening
  balances not adjusted at all, since excluding both entries means using
  the history before the closing as initial balance, and there is none in
  Odoo.

New question and entry lists
============================

When the first question is answered *Yes*, a second one is shown:
"Is this the first fiscal year recorded in Odoo?" (*¿Es el primer
ejercicio registrado en Odoo?*), and upstream's single closing/opening
entry fields are replaced by lists of entries:

* **No** (default, regular fiscal year): upstream logic, on several
  entries. Both "Previous fiscal year closing entries" (*Asientos de
  cierre del ejercicio anterior*) and "Opening entries" (*Asientos de
  apertura*) are required, and they are all excluded from the
  calculation, so the balances before the closing are the initial
  balance.
* **Yes** (first fiscal year recorded in Odoo): only the "Opening
  entries" are required. They are adjusted as initial balances (with the
  index of the month before the start date, as upstream does for the
  balances prior to it) instead of as movements of their month.

If the first question is answered *No*, nothing changes from upstream.

Validations and warnings
========================

Strict validations, which block the confirmation:

* the required lists above can't be empty;
* closing entries must be dated before the start date (the previous
  fiscal year's ones: the current fiscal year's closing would leave the
  previous closing in the initial balance, zeroing it out), and opening
  entries within the adjusted period.

Warnings, shown on top of the wizard as soon as the entries are selected,
which don't block the confirmation:

* regular fiscal year: the selected closing and opening entries don't
  cancel each other out in some accounts (an entry is missing or was
  selected by mistake, e.g. a result closing entry);
* first fiscal year in Odoo: some balances prior to the start date would
  also count as initial balance, besides the opening entries (e.g. the
  same balances loaded twice, or it's not really the first fiscal year in
  Odoo). Balances the opening entries cancel out, such as a bridge account
  used to load the pending invoices, don't trigger it.

Only non-monetary accounts carrying their balance forward are considered,
as in the adjustment itself: pending receivables/payables loaded before
the start date, and their taxes, are monetary and don't affect the
calculation.

Translation fix
===============

The wizard's "Journal" field had no Spanish translation upstream. It is
now translated as *Diario*.

Technical note
==============

Upstream builds the move line domain used for both the initial balance
and every period in a single method, ``get_move_line_domain()``, which
this module extends with ``super()`` to exclude the selected entries.

Upstream has no hook to move entries of the period into the initial
balance, so on the first fiscal year in Odoo the opening entries are
excluded through that same method, and ``confirm()`` adds their initial
balance adjustment lines (plus their own total line on the adjustment
account) to the draft entry upstream's ``confirm()`` creates, called with
``super()``. If upstream finds nothing else to adjust, this module creates
the entry with the opening entries' lines alone. Upstream's single
closing/opening entry fields are hidden and always left empty.

The "Journal" translation targets ``l10n_ar_account_reports``'s own field,
so it is written by hand in this module's ``.po`` files: Odoo's
translation export doesn't include it, keep it when regenerating them.
