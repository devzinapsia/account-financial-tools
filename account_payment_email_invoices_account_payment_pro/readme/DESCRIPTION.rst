Glue between *Facturas adjuntas al enviar órdenes de pago y recibos*
(``account_payment_email_invoices``) and ingadhoc's *Account Payment Super
Power* (``account_payment_pro``). Installed automatically when both are.

With ``account_payment_pro``, a **payment bundle** (``l10n_ar_payment_bundle``)
is a main payment without journal entry of its own, plus linked payments
(one per payment method) that settle the debts. When the main payment is
sent by email, this module attaches the documents settled by its linked
payments, including the credit notes applied within the bundle.

Payments of ``account_payment_pro`` that are not bundles already work with
the base module: it detects the credit notes applied within the payment
order or receipt (reconciled with an invoice in the same operation), and a
partial payment only attaches the debts it actually reached, not every debt
selected in it.
