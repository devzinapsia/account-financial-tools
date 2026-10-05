No specific configuration is required beyond the standard Argentinian
localization setup:

- The ``l10n_ar`` module must be installed.
- Purchase journals that should be compared must have **Use Documents**
  enabled (**Accounting ‣ Configuration ‣ Journals ‣ Journal ‣ Advanced
  Settings**).
- The current company's Tax ID (**Settings ‣ Companies**) must match the
  CUIT used to download the ARCA export, since the file's recipient CUIT is
  validated against it before importing.

Access: the whole process (running the **My Vouchers** wizard, viewing
runs and their results, **Reprocess** from the run form or from either
Action menu, and deleting runs) is available to users with **Show Full
Accounting Features** (``account.group_account_user``) and above, which
includes Accounting Administrators. Users with only **Billing** access
don't see the ARCA menu. No Documents app rights are needed: the source
file is stored and read back by the module itself.
