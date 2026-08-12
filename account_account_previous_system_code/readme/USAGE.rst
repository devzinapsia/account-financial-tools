Go to **Accounting ‣ Configuration ‣ Chart of Accounts**, open an account,
and fill in the **Previous system account code** field next to the
account's **Code**.

The column is available in the chart of accounts list (hidden by default;
enable it from the column selector) and the field can be used from the
search bar to look up an account by its previous system code.

If you try to save two accounts sharing a company with the same previous
system account code, Odoo raises a validation error. Leaving the field
empty is always allowed, even on multiple accounts at once.
