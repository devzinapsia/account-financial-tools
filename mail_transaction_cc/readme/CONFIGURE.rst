Go to **Accounting ‣ Configuration ‣ Accounting ‣ Email copies** (only
for *Accounting / Administrator* users) and create one rule per need:

* **Transaction type**: customer invoice, receipt, payment order,
  quotation / sales order, request for quotation / purchase order,
  customer communication or vendor communication (only types whose
  application is installed are offered).
* **Company**: the rule applies to documents of this company, whatever
  the company the sending user is working in.
* **Scope**:

  * *All communication* (default): document sending, messages sent to
    the customer or vendor from the record's chatter, and forwarding of
    incoming emails.
  * *Document sending only*: the sending wizards (single and batch),
    background sending, and automatic reminders of the document (e.g.
    the sales order confirmation email or the purchase receipt
    reminder).

  Customer and vendor communication have no document of their own, so
  their scope is always *All communication* and the field is hidden.

* **Additional condition**: optional domain on the transaction (e.g. a
  journal or an amount). Leave it empty to apply the rule to every
  record of the type.
* **Visible copy (Cc)**: free emails (separated by commas or
  semicolons), users, groups (members resolved when the email is sent),
  and **Include the responsible** (salesperson of the invoice, of the
  sales order or of the customer; creator of the payment; buyer of the
  purchase order or of the vendor, when Purchase is installed).
* **Hidden copy (Bcc)**: free emails, users and groups.

A rule needs at least one recipient. When a document matches several
rules, all their addresses are merged.
