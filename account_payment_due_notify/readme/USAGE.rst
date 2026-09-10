Once enabled, this module works entirely on its own -- there is nothing
to trigger by hand.

Every 30 minutes, for each company with the feature enabled, it checks
whether the current time (in that company's configured timezone) falls
in the same 30-minute window as the configured notification time. When
it does, it looks at every posted, unreconciled payable journal item with
a vendor and a due date, and for each one:

* If the number of days left until the due date matches the configured
  first-notice value, and the first notice has not been sent yet, it
  sends the first notice.
* If a second notice is enabled and the number of days left matches the
  configured second-notice value, and the second notice has not been
  sent yet, it sends the second notice.

Both checks are independent, so a document can receive both notices in
separate runs, or even on the same day if the two configured values
coincide. Each notice is sent once per document: sending it stamps the
document with the date and time it was sent, so it is never sent twice.
A document that gets reconciled or paid before its turn comes up simply
stops matching the criteria above, so no further notices go out for it.

All documents due on the same run for the same notice are sent as a
**single email**, not one email per document -- if five bills are due
in 3 days, that is one email listing all five, not five separate ones.
Its subject is **"Vencimientos a pagar hoy"** when the notice is for the
same day, or **"Vencimientos a pagar en ## días"** otherwise, where
``##`` is the configured number of days. The body lists, for every
document in that batch, its type and number (with a link to it), the
vendor, the reference, the due date, and the amount due; if any
**Accounts to report balance** are configured, their current balance is
added at the foot of the email.

Each notice is sent through the standard Odoo notification system, so
every configured user gets it by email or as an internal notification
according to their own preference (**Settings ‣ Preferences ‣
Notification**).
