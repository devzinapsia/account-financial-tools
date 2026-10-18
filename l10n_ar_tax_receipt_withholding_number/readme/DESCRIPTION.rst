The payment receipt / payment order PDF of ``l10n_ar_tax`` (Adhoc) lists
each withholding as a row of the payments table, showing only the tax
label (e.g. ``Ret IIBB MZA``). The withholding certificate number is only
available in the separate certificate report.

This module appends each withholding's own certificate number to its
label, for example ``Ret IIBB MZA - Cert. No. 0001-00000123``. When a
payment has several withholdings (several jurisdictions, or Earnings, VAT,
SUSS, etc.), every row shows the number of its own withholding line.

Lines without a number yet (draft payments) or with the ``/`` placeholder
keep showing the tax label only. The change applies to every document
printed with that template: supplier payment orders and customer receipts
(where the number is the certificate issued by the customer). Amounts and
columns are untouched.
