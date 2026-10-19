#. As an allowed user, create a vendor bill (or vendor credit/debit note)
   as usual.
#. In **Pay now journal**, pick the petty cash journal the bill was paid
   with. Only the journals that bypass authorization are offered. The
   bill no longer matches any authorization policy, unless an *Always
   block* policy matches it.
#. Click **Confirm**. The bill is confirmed, a payment from that journal is
   created, posted and reconciled with it, and the chatter records that
   the authorization was bypassed and with which journal.

Notes:

* Users who are not allowed to use the bypass see the *Pay now journal*
  as read-only, and can't confirm a bill that has one (they get an error).
  They can still load bills without a pay now journal, which go through
  the normal authorization flow: once confirmed, they can't be paid until
  they are authorized.
* Clearing the pay now journal puts the bill back into the normal
  authorization flow.
* A bill that requires authorization can't be paid on confirmation with
  a pay now journal that does not bypass authorization (see
  *Autorización de facturas de proveedor - Payment Pro*,
  ``account_vendor_bill_authorization_payment_pro``).
