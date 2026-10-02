Some vendor bills are already paid when they are loaded -- typically from a
petty cash (*Fondo Fijo*) journal. Requiring an authorization (see
*Autorización de facturas de proveedor*, ``account_vendor_bill_authorization``)
for something that is already paid makes no operational sense.

This module builds on the **Pay now journal** (*Diario de pago directo*,
field ``pay_now_journal_id``) of ingadhoc's *Account Payment Super Power*
(``account_payment_pro``): a journal chosen on a draft vendor bill, which
automatically creates, posts and reconciles a payment from that journal as
soon as the bill is confirmed.

When the company configures **journals that bypass authorization** and the
**users allowed to use this bypass**:

* On vendor bills and vendor credit/debit notes, the *Pay now journal*
  selector only offers those journals, and only those users can set it.
* A bill whose pay now journal is one of those journals **does not require
  authorization**: no authorization policy is applied, its authorization
  status is *Not required*, and it can be confirmed directly.
* **Always block wins over the bypass.** If a policy marked *Always block*
  matches the bill, it stays blocked whatever its pay now journal.
* Only an allowed user can confirm a bill that has a pay now journal. Any
  other user gets an error, and the bill stays in draft.
* The payment created on confirmation also **skips vendor payment
  authorization** (*Autorización de pagos a proveedores*,
  ``account_payment_authorization``): the bill and its payment are
  confirmed together. Only a payment from a bypass journal that settles
  bills whose pay now journal is that same journal gets this. Payment
  policies marked *Always block* still block it.
* When a bill is confirmed through the bypass, a message in its chatter
  records which journal bypassed the authorization.

A bill without a pay now journal follows the normal authorization flow,
unchanged.

The whole module is inactive while the *Allow pay now on vendor invoices?*
setting is unchecked, or while no journal that bypasses authorization is
configured.

This module was built for a specific client's setup. It depends on
``account_payment_authorization``, as well as on ``account_payment_pro``
and ``account_journal_security`` (ingadhoc).
