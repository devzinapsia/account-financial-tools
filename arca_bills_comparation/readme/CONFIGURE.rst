No specific configuration is required beyond the standard Argentinian
localization setup:

- The ``l10n_ar`` module must be installed.
- Purchase journals that should be compared must have **Use Documents**
  enabled (**Accounting ‣ Configuration ‣ Journals ‣ Journal ‣ Advanced
  Settings**).
- The current company's Tax ID (**Settings ‣ Companies**) must match the
  CUIT used to download the ARCA export, since the file's recipient CUIT is
  validated against it before importing.

Access to the wizard and its results follows the same security groups as
vendor bills: ``Billing`` users can run the process and view results;
``Accounting Manager`` users additionally get full read/write access to
stored runs and lines.
