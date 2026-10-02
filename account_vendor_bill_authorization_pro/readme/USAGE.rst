#. As an allowed user, create a vendor bill (or vendor credit/debit note)
   as usual.
#. In **Pay now journal**, pick the petty cash journal the bill was paid
   with. Only the journals that bypass authorization are offered. The
   **Authorization** status changes to *Not required*, unless an *Always
   block* policy matches the bill.
#. Click **Confirm**. The bill is confirmed, a payment from that journal is
   created, posted and reconciled with it, and the chatter records that
   the authorization was bypassed and with which journal.

Notes:

* Users who are not allowed to use the bypass see the *Pay now journal*
  as read-only, and can't confirm a bill that has one (they get an error).
  They can still load bills without a pay now journal, which go through
  the normal authorization flow.
* Choosing the pay now journal on a bill that was already authorized or
  rejected discards that decision: the bill no longer requires
  authorization.
* Clearing the pay now journal puts the bill back into the normal
  authorization flow.
