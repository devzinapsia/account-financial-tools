Importing a bank statement file works the same way as before (from the
bank journal, **Upload**), with these differences:

- If your bank's export has a free-text legend/description column that
  sometimes contains the counterparty's CUIT, map that column to
  **Contact (CUIT in free-text legend)** instead of (or in addition to)
  mapping a real partner column.
- If a row looks like a movement you already imported for this journal
  (same date, contact and amount), it is skipped automatically and
  reported in the import result - check the warning message if the
  number of imported lines looks lower than expected. The full detail
  (which existing line each skipped row matches) is on the resulting
  statement's chatter.
- Reimporting the exact same file for the same journal is rejected
  outright, with a reference to the statement that already has it.
- If you're sure the flagged rows are *not* duplicates, check **Import
  even if rows look like duplicates** in the import screen's options
  sidebar (left side, under "Use first row as header") before importing
  again. It's only shown for bank statement imports, and it's remembered
  per journal like the column mapping - only when checked, though:
  unchecking it goes back to the default (checking for duplicates).
- Right above that same checkbox is **Automatically reconcile when
  contact, date and amount match** - checked by default. With it on, right
  after a real import, every line still unreconciled (once Odoo's own
  native matching is done with it) gets one more pass: if there's a unique
  open invoice/payment with the same date and amount - and, when the line
  already has a contact, the same partner too - it gets reconciled
  automatically. Uncheck it for a specific import if you'd rather review
  and reconcile those lines by hand; like the checkbox above, the choice
  is remembered per journal.

On the bank reconciliation screen, use **Reconcile by date and amount**
(⚙ cog menu, top right) to run that same on-demand, for every unreconciled
line of the journal being reconciled (no selection needed) against a
unique open invoice/payment with the same date and amount (and the same
contact, when the line already has one).

Deleting a bank statement with reconciled lines now shows a confirmation
warning before unreconciling and removing them.
