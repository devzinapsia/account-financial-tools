Once enabled, this module works entirely on its own -- there is nothing
to trigger by hand.

Every 30 minutes, for each company with the feature enabled, it checks
whether the current time (in that company's configured timezone) falls
in the same 30-minute window as the configured notification time. When
it does, it looks at every posted, unreconciled payable journal item with
a vendor and a due date, and for each one:

* If the number of days left until the due date matches the configured
  first-notice value, it sends the first notice.
* If a second notice is enabled and the number of days left matches the
  configured second-notice value, it sends the second notice.

Both checks are independent, so a document can receive both notices in
the same run if the two configured values coincide. There is no
per-document "already notified" tracking: each run simply sends
whatever currently matches, in full, as if it were the first time. In
practice this means each notice normally goes out once, since a
document's days-left count only equals a given configured value on one
specific day -- but if the notification time is reconfigured mid-day,
or the check is triggered by hand more than once, the same set is sent
again rather than being silently skipped; there is nothing to get stuck
if a due date is corrected later, either (reset to draft, fix the date,
post again -- the next run picks it up under the new date with no
extra step). A document that gets reconciled or paid before its turn
comes up simply stops matching the criteria above.

All documents due on the same run for the same notice are sent as a
**single email**, not one email per document -- if five bills are due
in 3 days, that is one email listing all five, not five separate ones.

Its subject is **"Vencimientos a pagar hoy en <company>"** when the
notice is for the same day, or **"Vencimientos a pagar en ## días en
<company>"** otherwise, where ``##`` is the configured number of days
and ``<company>`` is this company's name. The body starts with a bold
**"Comprobantes a pagar el día: ##/##/####"** line, then a table with,
for every document in that batch, the vendor, its type and number (with
a small calendar-icon link to it), the reference, and the amount due,
right-aligned; if any **Accounts to report balance** are configured,
their current balance (name only, no account code) is added at the foot
of the email under a bold **"Saldo de bancos y efectivo"** heading, also
right-aligned.

If **Send a weekly payment due summary (Mondays)** is checked, every
Monday -- in the same notification window as the daily notices above --
a separate digest is sent listing every payable document due that same
Monday through the following Sunday, sorted ascending by due date (with
the due date as its own first column, since unlike the daily digest a
week can span several different dates). Its subject is
**"Vencimientos a pagar esta semana (##-##-#### a ##-##-####) en
<company>"**. Unlike the daily notices, it does track (per company)
the last Monday it was sent for, so it only goes out once per Monday
even if the check runs more than once in that day's window.

Each notice is sent through the standard Odoo notification system, so
every configured user gets it by email or as an internal notification
according to their own preference (**Settings ‣ Preferences ‣
Notification**). No mail signature is appended.
