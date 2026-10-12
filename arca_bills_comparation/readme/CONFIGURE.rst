No specific configuration is required beyond the standard Argentinian
localization setup:

- The ``l10n_ar`` module must be installed.
- Purchase journals that should be compared must have **Use Documents**
  enabled (**Accounting ‣ Configuration ‣ Journals ‣ Journal ‣ Advanced
  Settings**).
- The current company's Tax ID (**Settings ‣ Companies**) must match the
  CUIT used to download the ARCA export, since the file's recipient CUIT is
  validated against it before importing.

Amount tolerance (**Accounting ‣ Configuration ‣ Settings ‣ Vendor Bills ‣
ARCA comparison tolerance**, per company):

- **Amount**: maximum difference, in the company currency, still reported
  as a match. Defaults to 0.02, to absorb rounding differences.
- **Percentage**: maximum difference as a percentage of ARCA's amount.
  Defaults to 0 (off).
- The larger of both is evaluated separately for each amount compared on
  each voucher (total, net amounts and taxes), e.g. "up to $1 or up to
  0.1% of that amount, whichever is larger".
  **Reprocess** always uses the current settings; each run shows the
  tolerances its last processing used.

Access: the whole process (running the **My Vouchers** wizard, viewing
runs and their results, **Reprocess** from the run form or from either
Action menu, and deleting runs) is available to users with **Show Full
Accounting Features** (``account.group_account_user``) and above, which
includes Accounting Administrators. Users with only **Billing** access
don't see the ARCA menu. No Documents app rights are needed: the source
file is stored and read back by the module itself.
