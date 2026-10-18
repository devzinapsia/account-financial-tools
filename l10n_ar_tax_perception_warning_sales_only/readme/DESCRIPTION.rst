The ``l10n_ar_tax`` module (Adhoc) shows a warning banner on the invoice
form when the fiscal position has perception taxes and the invoice date is
still empty, explaining that perceptions will be recomputed when the date
is set or the invoice is posted.

Perceptions are only added on sale documents, but fiscal positions are
auto-detected by contact (ARCA responsibility type), not by document type.
A Registered VAT supplier therefore gets the perceptions fiscal position on
its vendor bills too, and the banner shows up there, where it is easily
confused with the perceptions charged by the supplier.

This module keeps the banner only on customer invoices, customer credit
notes and sales receipts. Nothing else changes: the fiscal position is
still detected on vendor bills (it does not alter their taxes), and the
perception computation of ``l10n_ar_tax`` is untouched.
