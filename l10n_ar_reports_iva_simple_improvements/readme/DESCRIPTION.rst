This module corrects and improves the determination of the "Concepto"
(Bien / Locación / Servicio / Bien de Uso) column on the purchase files
(CREDITO / REST_CREDITO) of the "IVA Simple" report exported by Odoo
Enterprise's ``l10n_ar_reports_simple`` (ARCA, ex-AFIP, mandatory since
November 2025 under RG 5705/2025 for VAT-registered taxpayers).

Bug fixed
=========

Upstream determines the Concepto for each purchase line using 2 account
tags (*Bienes de Uso*, *Locaciones*) and, when neither tag nor a product
is available on the line, blindly falls back to Concepto 1 (Bien). In
real data, a purchase line without a product is almost always a services
expense billed without itemized products (e.g. a services invoice with
just a description, no product line), so that fallback silently
misclassifies most of those lines as goods instead of services.

New Concepto priority
======================

This module adds 2 new account tags, so all 4 ARCA concepts can be set
explicitly on an account, and replaces the determination logic with this
priority (highest to lowest):

#. Account tagged *Locaciones* → Concepto 2
#. Account tagged *Bienes de Uso* → Concepto 4
#. Account tagged *Servicios* (new) → Concepto 3
#. Account tagged *Bienes* (new) → Concepto 1
#. No tag, but the line has a product: ``type == 'consu'`` → Concepto 1,
   ``type == 'service'`` → Concepto 3
#. No tag and no product → Concepto 3 (Servicio). This is the bug fix:
   upstream falls back to Concepto 1 here.

A constraint on ``account.account`` blocks assigning more than one of
these 4 tags to the same account at the same time, since the report
logic can only use one.

Technical note
==============

The upstream CASE that derives the Concepto is inlined inside one large
raw SQL query built in Python
(``_vat_simple_build_purchase_query``) - there is no smaller method to
override just that fragment. This module therefore fully overrides that
method, duplicating the rest of the query unchanged (moves/taxes
selection, aggregation, column mapping) and only changing the tag
lookup, the CASE, the tie-break ``ORDER BY``, and the final fallback.
This is more legible and testable than the alternative considered (a
computed field on ``account.account`` resolving the concept per account),
since the join/priority logic still has to live inside the same SQL
query either way; the trade-off is that this module can fall out of sync
if a future Odoo upgrade changes the upstream query - review this
override whenever ``l10n_ar_reports_simple`` is upgraded.

Sales files (DEBITO / REST_DEBITO) are not affected: ARCA does not use
the Concepto field there (they use "Tipo de Operación" instead), and
that logic was already correct.
