Go to **Accounting ‣ Configuration ‣ Settings** and, under the
"Bank & Cash" area, enable or disable **Account reconciliation** (leave
statement lines reconciled automatically - either on import or by a
reconciliation model - flagged to check; enabled by default).

In the same area, disable **Only auto-reconcile through outstanding
accounts** if bank statement lines in this company do *not* always
settle through a receipt/payment order - leave it enabled (the default)
for a company whose bookkeeping always goes through one, so Odoo's own
automatic reconciliation never matches a statement line straight to an
invoice/bill instead.

Also in the same area, disable **Pre-filter the journal in the
reconciliation search dialog** for a company with few enough bank
journals that seeing every candidate from every bank in "Search: Journal
Items to Match" is never in the way. Enabled by default - useful for a
company with many bank journals.

No other configuration is required: the per-journal import mapping is
learned automatically the first time you import a file for that journal,
and the CUIT recognition works on whichever column you map to the new
"Contact (CUIT in free-text legend)" field - or, for banks with no
separate legend column (e.g. BBVA's "Concepto"), the "Label + Contact
(CUIT in free-text legend)" field - in the import wizard.
