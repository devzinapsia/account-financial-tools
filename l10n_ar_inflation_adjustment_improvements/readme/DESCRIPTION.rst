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

Simulation and detail report
============================

The wizard has 2 more buttons next to **Confirm**: **Simulate PDF** and
**Simulate Excel**. They download the adjustment detail without creating
the entry, so it can be checked, and simulated again with other
parameters, before confirming. The report is the "Detail of the result
from exposure to changes in the purchasing power of the currency"
(*Detalle del resultado por exposición a los cambios en el poder
adquisitivo de la moneda*), one block per account with its origin index,
coefficient (as a factor and as %), debit/credit, adjustment, final
adjustment and historical/restated balance, plus a summary by account
whose total equals the adjustment account counterpart. The report is A4
portrait, the same layout as the RECPAM detail of the previous accounting
system, plus the summary.

Report detail options
---------------------

The wizard's "Report detail" (*Detalle del reporte*) sets the PDF's rows:

* **By account and month** (*Por cuenta y mes*, default): one row per
  account and origin month, as the adjustment entry lines. The shortest
  one, for the general review: each row's adjustment debit minus
  adjustment credit matches a line of the entry (to the cent, see
  Rounding below).
* **Balance sheet accounts by entry, income/expense by month**
  (*Patrimoniales por asiento, resultados por mes*): one row per journal
  entry on balance sheet accounts (fixed assets, equity, etc.), where each
  opening entry, purchase or contribution is worth seeing, and one row per
  month on income/expense accounts, which hold every invoice of the year.
* **By account and entry** (*Por cuenta y asiento*): one row per journal
  entry on every account, as a ledger grouped by entry (several lines of
  the same entry on the same account add up to one row). Each invoice is
  a journal entry in Odoo, so income/expense accounts can list hundreds
  of rows: for auditing a specific account rather than for printing.

The Excel file always has both the by month and the by entry details,
plus a summary, in separate sheets, to filter any combination.

Considerations
--------------

* **Header:** the report's subtitle is the report detail it was printed
  with, and it states the closing/opening entries the
  adjustment was computed with (closing and opening entries excluded on a
  regular fiscal year; opening entries adjusted as initial balance on the
  first fiscal year in Odoo), so it documents its own parameters.
* **Initial balance row:** the balances prior to the start date always
  add up to a single "Initial balance" row per account, even when
  detailed by entry (the history before the period isn't listed). On the
  first fiscal year in Odoo, the by month detail also adds the opening
  entries into that row; the by entry details list each opening entry.
* **Opening entries index:** the initial balance and the first fiscal
  year's opening entries use the index of the month before the start
  date (e.g. June for a fiscal year starting on July 1st), since they
  carry the balances at the previous closing. The previous accounting
  system's RECPAM detail used the same criterion.
* **Coefficient:** shown both as a factor (closing index / origin month
  index, e.g. 1.3355) and as the % the adjustment applies (factor - 1,
  e.g. 33.55%, the same % as the adjustment entry line labels).
* **Debit and credit adjusted on their own:** upstream adjusts the net
  of each account and month (one line per month in the entry). The
  report adjusts each column on its own instead, debit × % in "Adjustment
  debit" and credit × % in "Adjustment credit", as the previous system's
  report did, so both sides of a month show their adjustment. The final
  adjustment is the same: their difference.
* **Rounding:** each row is rounded on its own, so a "Rounding
  difference" row shows up where their sum differs from the entry by a
  few cents. Account totals and the summary always match the entry.
* **Adjustment already recorded:** if a posted inflation adjustment entry
  already exists within the period (in the wizard's journal, on its
  adjustment account), the wizard and the report warn about it: its lines
  count as movements of the period (dated on the last month they don't
  change the adjustment, but they do change the historical balances), and
  confirming again would record the adjustment twice. Reset it to draft
  or cancel it before recalculating.

Chatter
-------

On **Confirm**, whether or not it was simulated before, 2 files are
attached to the adjustment entry and posted in its chatter, as the
working papers of that adjustment:

* the **PDF**, with the report detail selected in the wizard (by account
  and month by default), to read or print;
* the **Excel** file, the most detailed one, with every detail.

Simulations are only downloaded: they aren't attached to any entry.

To match the entry to the cent without duplicating upstream's
calculation, the simulation creates the adjustment entry exactly as
**Confirm** would, reads it and rolls everything back.

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
