Go to **Invoicing / Accounting ‣ Configuration ‣ Invoicing ‣ Invoice Classifications**
and create the classifications your company needs.

Each classification record has:

- **Name** (required, translatable)
- **Code** (optional shorthand, shown as ``[CODE] Name`` in dropdowns)
- **Color** (integer 0–11, maps to Odoo's tag colour palette)
- **Sequence** (controls display order)
- **Company** (leave empty to make the classification available company-wide)

Only users with the *Accounting Manager* group can create, edit, or delete
classifications. Users with at least the *Billing* group can read them and assign
them to invoices.
