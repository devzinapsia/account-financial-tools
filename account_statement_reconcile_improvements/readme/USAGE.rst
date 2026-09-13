Importing a bank statement file works the same way as before (from the
bank journal, **Upload**), with these differences:

- If your bank's export has a free-text legend/description column that
  sometimes contains the counterparty's CUIT, map that column to
  **Contact (CUIT in free-text legend)** instead of (or in addition to)
  mapping a real partner column.
- If a row looks like a movement you already imported for this journal
  (same date, contact and amount), it is skipped automatically and
  reported in the import result - check the warning message if the
  number of imported lines looks lower than expected.
- Reimporting the exact same file for the same journal is rejected
  outright, with a reference to the statement that already has it.

On the bank reconciliation screen, use the new **Auto-reconcile
unassigned** button to try to match every unassigned, unreconciled line
against a unique open invoice/payment with the same date and amount.

Deleting a bank statement with reconciled lines now shows a confirmation
warning before unreconciling and removing them.
