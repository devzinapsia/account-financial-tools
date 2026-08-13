Registering a payment
======================

Open a vendor bill and click **Register Payment** as usual (or select a
single vendor bill from the Vendor Bills list and use the same action).

* If the payment does not match any authorization scheme, or the user
  registering it is already an authorized user on every matching scheme,
  the payment is confirmed immediately, exactly as before this module was
  installed.
* If the payment matches at least one scheme and the user registering it
  is **not** an authorized user on any matching scheme, the payment is
  **not** confirmed. Instead:

  * Its **Authorization status** is set to *To authorize*.
  * An activity is assigned to every authorized user of every matching
    scheme, so it shows up in their **My Activities** and triggers an
    email according to their own notification preferences.
  * A message is logged on the payment's chatter noting that
    authorization was requested and from whom.
  * The user who tried to confirm the payment gets an error message
    explaining that the payment is now pending authorization.

Approving or rejecting a pending payment
=========================================

Open the payment (it will be in the *To authorize* state) and go to its
**Authorization** tab. If you are one of the users authorized to approve
it, you will see **Approve** and **Reject** buttons there.

* **Approve**: confirms the payment right away, sets the **Authorized
  by** field to you, and marks the pending activities as done.
* **Reject**: opens a small window asking for a reason. Once confirmed,
  the payment's **Authorization status** becomes *Rejected*, the reason
  is stored on the payment, the pending activities are marked done, and
  an activity is created for the user who originally registered the
  payment, informing them of the rejection and the reason.

Only users who are actually listed as authorizers on a matching scheme
can approve or reject a payment -- this is enforced on the server, not
just by hiding the buttons.

Finding pending payments
=========================

The **Vendor Payments** list (Accounting ‣ Vendors ‣ Payments) offers two
extra filters in the search bar:

* **To authorize**: payments currently waiting for any authorization.
* **To authorize by me**: payments you are personally allowed to
  approve or reject right now.

The **Authorization status** column is also available (hidden by
default; enable it from the column selector).
