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
