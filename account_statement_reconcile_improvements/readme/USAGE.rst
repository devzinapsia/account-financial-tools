Importing a bank statement file works the same way as before (from the
bank journal, **Upload**), with these differences:

- If your bank's export has a free-text legend/description column that
  sometimes contains the counterparty's CUIT, map that column to
  **Contact (CUIT in free-text legend)** instead of (or in addition to)
  mapping a real partner column.
- If your bank's export has no separate legend column - the transaction's
  own label is the only place the CUIT shows up (e.g. BBVA's "Concepto") -
  map that column to **Label + Contact (CUIT in free-text legend)**
  instead: it keeps the column's text as the line's label and resolves
  the contact from it at the same time.
- If a row looks like a movement you already imported for this journal
  (same date, contact and amount), it is skipped automatically and
  reported in the import result - check the warning message if the
  number of imported lines looks lower than expected.
- Reimporting the exact same file for the same journal is rejected
  outright, with a reference to the statement that already has it.
- If you're sure the flagged rows are *not* duplicates, check **Import
  even if rows look like duplicates** in the import screen's options
  sidebar (left side, under "Use first row as header") before importing
  again. It's only shown for bank statement imports, and it's remembered
  per journal like the column mapping - only when checked, though:
  unchecking it goes back to the default (checking for duplicates).

On the bank reconciliation screen, use **Reconcile by date and amount**
(⚙ cog menu, top right) to try to match every unassigned, unreconciled
line of the journal being reconciled against a unique open
invoice/payment with the same date and amount.

Deleting a bank statement with reconciled lines now shows a confirmation
warning before unreconciling and removing them.

On the bank reconciliation screen, use **Create Bill** (in the "..."
dropdown, below "Upload Bills") to open a blank vendor bill for a line you
don't have a receipt/invoice file for yet, instead of attaching a
placeholder file just to get past "Upload Bills".
