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

Authorizing or rejecting a pending payment
=============================================

Open the payment (it will be in the *To authorize* state). If you are one
of the users authorized to act on it, you will see an **Authorize**
button next to **Confirm** in the header, and a **Reject** button in the
**Authorization** tab.

* **Authorize**: does *not* confirm the payment. It only sets the
  **Authorization status** to *Authorized* and the **Authorized by**
  field to you, marks the pending activities as done, and logs it on the
  chatter. The payment stays in *Draft*.

  Once a payment is authorized this way, **anyone** with the normal
  permission to confirm payments can click the regular **Confirm**
  button to actually post it -- it no longer needs to be an authorized
  user, since the authorization already happened. This lets the person
  who signs off on a payment be different from the person who actually
  executes it.

  As a shortcut, if the user confirming the payment is themselves an
  authorized user for a matching scheme, clicking **Confirm** directly
  (without using **Authorize** first) still authorizes and confirms it
  in one step, exactly as before.
* **Reject**: opens a small window asking for a reason. Once confirmed,
  the payment's **Authorization status** becomes *Rejected*, the reason
  is stored on the payment, the pending activities are marked done, and
  an activity is created for the user who originally registered the
  payment, informing them of the rejection and the reason.

Only users who are actually listed as authorizers on a matching scheme
can authorize or reject a payment -- this is enforced on the server, not
just by hiding the buttons. Every authorization event (who authorized,
who confirmed, who rejected and why) is logged on the payment's chatter,
timestamped.

Finding pending payments
=========================

The **Vendor Payments** list (Accounting ‣ Vendors ‣ Payments) offers two
extra filters in the search bar:

* **To authorize**: payments currently waiting for any authorization.
* **To authorize by me**: payments you are personally allowed to
  approve or reject right now.

The **Authorization status** column is also available (hidden by
default; enable it from the column selector).
