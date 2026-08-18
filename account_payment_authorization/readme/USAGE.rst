Registering a payment
======================

Open a vendor bill and click **Register Payment** as usual (or select a
single vendor bill from the Vendor Bills list and use the same action).

* If the payment does not match any authorization policy, or the user
  registering it is already an authorized user on every matching policy,
  the payment is confirmed immediately, exactly as before this module was
  installed.
* If the payment matches at least one policy and the user registering it
  is **not** an authorized user on any matching policy, the payment is
  **not** confirmed. Instead:

  * Its **Authorization status** is set to *To authorize*.
  * An activity is assigned to every authorized user of every matching
    policy, so it shows up in their **My Activities** and triggers an
    email according to their own notification preferences.
  * A message is logged on the payment's chatter noting that
    authorization was requested and from whom.
  * The user who tried to confirm the payment gets an error message
    explaining that the payment is now pending authorization.

Authorizing or rejecting a pending payment
=============================================

Open the payment. If you are one of the users authorized to act on it,
you will see an **Authorize** button next to **Confirm** in the header,
and a **Reject** button in the **Authorization** tab -- available as soon
as the payment is a draft that matches a policy you can act on, even if
nobody has attempted to confirm it yet. It is not necessary to wait for
someone else to first try **Confirm** and be blocked from it (which is
what sets the **Authorization status** to *To authorize*): this matters
because, in practice, the person who registers the payment is often not
themselves an authorized user, so they could never be the one to trigger
that state.

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
  authorized user for a matching policy, clicking **Confirm** directly
  (without using **Authorize** first) still authorizes and confirms it
  in one step, exactly as before.

  Authorized by mistake? While the payment is still a draft (i.e. not
  confirmed yet), an **Unauthorize** button appears next to **Confirm**.
  It reverts the **Authorization status** back to *To authorize*, clears
  **Authorized by**, logs it on the chatter, and notifies the user who
  originally registered the payment. The payment can be authorized again
  afterwards, by the same or a different authorizer, with no
  restriction.
* **Reject**: opens a small window asking for a reason. Once confirmed,
  the payment's **Authorization status** becomes *Rejected*, the reason
  is stored on the payment, the pending activities are marked done, and
  an activity is created for the user who originally registered the
  payment, informing them of the rejection and the reason.

Only users who are actually listed as authorizers on a matching policy
can authorize or reject a payment -- this is enforced on the server, not
just by hiding the buttons. Every authorization event (who authorized,
who confirmed, who rejected and why) is logged on the payment's chatter,
timestamped.

Editing an already-authorized payment (amount, vendor, payment method,
journal, currency, date, or which bill it settles) before it's confirmed
throws away that authorization: its **Authorization status** goes back
to *To authorize*, **Authorized by** is cleared, and this is logged on
the chatter, so a payment can't be authorized for one amount and then
confirmed after being changed to a different one.

Finding pending payments
=========================

The **Vendor Payments** list (Accounting ‣ Vendors ‣ Payments) offers
extra filters in the search bar:

* **To authorize**: payments currently waiting for any authorization.
* **To authorize by me**: payments you are personally allowed to
  approve or reject right now.
* **Authorized, not confirmed by me yet**: payments you registered
  yourself that needed authorization, already got it, and are still
  sitting as a draft waiting to be confirmed -- easy to lose track of
  among other drafts otherwise, since nothing else singles them out
  once they are no longer *To authorize*.

The **Authorization status** column is also available (hidden by
default; enable it from the column selector).
