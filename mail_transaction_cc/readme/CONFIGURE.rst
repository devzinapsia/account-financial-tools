Go to **Accounting ‣ Configuration ‣ Accounting ‣ Email copies** (only
for *Accounting / Administrator* users) and create one rule per need:

* **Transaction type**: customer invoice, receipt, payment order or
  purchase (only types whose application is installed are offered).
* **Company**: the rule applies to documents of this company, whatever
  the company the sending user is working in.
* **Scope**:

  * *All communication* (default): document sending, messages sent to
    the customer or vendor from the record's chatter, and forwarding of
    incoming emails.
  * *Document sending only*: the sending wizards (single and batch),
    background sending, and automatic reminders of the document (e.g.
    the purchase receipt reminder).

* **Additional condition**: optional domain on the transaction (e.g. a
  journal or an amount). Leave it empty to apply the rule to every
  record of the type.
* **Visible copy (Cc)**: free emails (separated by commas or
  semicolons), users, groups (members resolved when the email is sent),
  and **Include the responsible** (salesperson of the invoice, creator
  of the payment, buyer of the purchase order).
* **Hidden copy (Bcc)**: free emails, users and groups.

A rule needs at least one recipient. When a document matches several
rules, all their addresses are merged.
