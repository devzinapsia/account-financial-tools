Go to **Accounting ‣ Configuration ‣ Settings**, in the **Vendor
Payments** section, under **Payment due notifications**:

* **Notify on payment due dates**: master switch for this company. All
  other fields below only show once this is checked.
* **Days before due date (first notice)**: how many days before a
  document's due date the first notice is sent. 0 means the same day it
  is due. Default: 3.
* **Send a second notice**: optional second notice. If unchecked, only
  the first notice above is ever sent, and the days field below is not
  evaluated at all. Default: checked.
* **Days before due date (second notice)**: how many days before the due
  date the second notice is sent, only used if **Send a second notice**
  is checked. 0 means the same day it is due. Default: 0.
* **Notification time**: approximate local time of day, in the timezone
  below, at which notices are sent. The check that sends notices runs
  every 30 minutes, so the actual send time can be up to 30 minutes
  after this.
* **Notification timezone**: timezone used to evaluate the time above.
  Suggested automatically from the company's country when every zone in
  that country currently shares the same UTC offset (e.g. Argentina);
  left empty otherwise (e.g. the US, Brazil) -- it is never assumed from
  the server, so set it explicitly if it is not suggested.
* **Users to notify**: the users who receive notices, restricted to
  internal users (portal/public users are not offered). This list is
  global per company; it does not vary by vendor or journal.
* **Accounts to report balance**: optional accounts, restricted to
  active accounts of type Bank and Cash, whose current balance is added
  at the foot of every notification email, as a quick reference for
  whether there are enough funds to pay. Leave empty to not include any
  balance information. This is only a reference: it does not account
  for pending collections, other scheduled payments, or checks in
  transit -- it is most useful when a notice is for "today".
