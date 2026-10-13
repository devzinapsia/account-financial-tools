Reviewing (reviewer)
--------------------

Go to **Accounting ‣ Vendors ‣ Payments to review**. It opens the
confirmed vendor payments filtered by *Pending review* and *Answered*; use
the standard filters and group-bys (date, journal, payment method, vendor,
amount) to pick which ones to review.

* **One payment**: open it and click **Mark as reviewed**. Choose *OK*, *With
  observations* (comment required) or *Not required*, plus an optional
  comment.
* **Several payments**: select them in the list and use **Actions ‣
  Mark as reviewed**. The wizard shows one line per payment, all set to *OK* by
  default; change the result and add a comment per line where needed
  (required for *With observations*). Remove a line to leave a payment
  out.

Every decision is posted in the payment's chatter as an internal message
authored by the reviewer (the reviewer's "signature"): who, when, the
result and the comment. Review messages are internal and never e-mailed
to the payment's followers.

The reviewer can change their mind at any time, e.g. turn a *Reviewed*
payment into *With observations* when something comes up at month end.

Answering observations (issuer)
-------------------------------

When the reviewer records observations, the user who confirmed the
payment gets a *Payment review observation* activity with the comment,
due in the configured number of days. Make whatever adjustment is needed
(this module never changes the payment) and answer in either of two
equivalent ways:

* mark the activity as done and write the answer in its feedback box
  (marking it done without an answer is refused, so the observation can't
  be left unanswered by mistake);
* or click **Answer observations** on the payment.

Either way the activity is closed, the answer is posted in the chatter,
the payment becomes *Answered* and the reviewer gets an activity to
review it again. Any accounting user can answer on the issuer's behalf.

The **My payments with observations** filter lists the issuer's own
payments still waiting for an answer.

Closing the review (reviewer)
-----------------------------

An *Answered* payment stays in the reviewer's **Payments to review** list
until the reviewer decides on it again: once the answer is read, either
mark the reviewer's activity as done (which signs the payment off as
*Reviewed*, the activity's feedback becoming the review comment), or use
**Mark as reviewed** to choose *OK* or record new observations.

Visibility
----------

* A colored badge next to the payment number in the payment lists:
  *Pending review* (blue), *Reviewed* (green), *With observations* (red),
  *Answered* (orange). *Not required* shows no badge.
* The same badge under the number on the payment form, and a **Review**
  tab with the reviewer, review date, issuer, comment and answer.
* Optional **Review status**, **Reviewer** and **Review date** columns in
  the vendor payments list, and **Review status** / **Reviewer** group-bys.
* The list's own **Journal** and **Payment method** columns tell which
  journal and payment method each payment used. With ingadhoc's payment
  bundles (pagos múltiples) they show the bundle's own journal and method
  instead of the actual ones: see the
  account_payment_review_payment_bundle module's README.

Permissions
-----------

* Only *Payment reviewers* can review or mark payments as not required,
  enforced on the server, not only by hiding buttons: review fields can't
  be changed through list editing, import or direct API calls either.
* A reviewer can't review a payment they created or confirmed themselves.
* Answering observations is open to the payment's issuer and to any user
  with the *Invoicing* accounting rights.
