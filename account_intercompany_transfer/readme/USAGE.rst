Making a transfer
-----------------

#. Go to **Accounting ‣ Accounting ‣ Transactions ‣ Intercompany
   transfers** (under **Accounting ‣ Bank and Cash** when ingadhoc's
   internal transfers are installed, see the bridge module
   ``account_intercompany_transfer_adhoc``) and click **New transfer**.
#. Pick the **origin journal**: the origin company and the currency follow
   from it.
#. Pick the **destination company** and the **destination journal**: only
   companies with a bridge account, and journals in the same currency as
   the origin journal, are offered.
#. Enter the **amount**, the **date** and an optional **memo**, and click
   **Confirm**.

The transfer opens posted, with a smart button to each payment. Each
payment is then reconciled with its bank statement line in its own
company, as any other payment. Opening the payment of a company that is
not ticked in the company switcher asks to select that company first.

The memo is the only field of a transfer that can be changed. Its payments
and their journal entries can't be modified, reset to draft, cancelled,
reversed nor deleted by hand: cancel the transfer instead.

Cancelling a transfer
---------------------

Click **Cancel** on a posted transfer: both payments are cancelled, in
both companies, in one single transaction, and the transfer becomes
*Cancelled*. It is not possible when:

* any journal item of either payment is reconciled, typically with a bank
  statement line: undo that reconciliation first;
* either payment is dated in a closed period of its company.

The message names the payment, its company and the reason. A cancelled
transfer can't be posted again: create a new one.

Finding transfers
-----------------

The transfers list can be filtered by status and by **Sent by the current
company** / **Received by the current company**, and grouped by origin
company, destination company, status or month. Each user sees the
transfers where the origin or the destination company is among their
allowed companies.

In the payments lists, the **Intercompany transfer** column (optional) and
search field show which transfer a payment belongs to.
