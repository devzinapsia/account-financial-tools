Sends the emails of certain transactions with internal addresses in
**visible copy (Cc)** for the customer or vendor, plus an optional
**hidden copy (Bcc)**.

Odoo sends one individual email per recipient partner, so adding
partners or followers never produces a real "Cc" header. This module
puts the copies in the *same* email the customer or vendor receives:
``To: customer`` and ``Cc: internal addresses`` in the real email
header, and the Bcc addresses in the SMTP envelope only (never visible
in the headers).

Supported transactions:

* **Customer invoice**: customer invoices and credit notes (debit notes
  included).
* **Receipt**: customer payments, in any direction (customer refunds
  included). Internal transfers are excluded.
* **Payment order**: vendor payments, in any direction (vendor refunds
  included). Internal transfers are excluded.
* **Quotation / sales order**: quotations and confirmed sales orders.
* **Purchase**: requests for quotation and purchase orders.

Sales and Purchase types become available automatically as soon as the
application is installed, without updating this module; this module
depends on neither of them.

It only depends on ``account`` and ``mail``, and works with or without
Adhoc's receiptbooks installed (their automatic receipt email is a
document sending too).
