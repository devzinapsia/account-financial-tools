When a **payment order** (outgoing payment) or a **receipt** (incoming
payment) is sent by email, this module also attaches the PDF of the invoices
and credit notes that intervene in that payment.

The attachments sent today (the payment receipt report and, with
``l10n_ar_tax``, the withholding certificates) are not touched nor reordered:
the documents are added **after** them.

Which documents are attached:

* The invoices and credit notes, of sales or purchases, **reconciled with
  the payment**.
* The credit notes **applied within the payment**: the payment wizards
  reconcile the payment, the invoices and the credit notes in a single
  operation, and a credit note then ends up reconciled with an invoice
  instead of with the payment. A credit note applied to the invoice before
  the payment, in another operation, did not intervene in the payment and is
  not attached.
* Only posted documents (never drafts nor cancelled ones), never twice, and
  only the ones the user can read.
* Each email carries the documents of **that** payment: a partial payment
  attaches the invoices it reached, and an invoice paid by several payments
  is attached to the email of each of them.
* Documents of the journals excluded in the settings (e.g. the document
  adjustment journals loaded by the Go Live) are never attached.

Which PDF:

* **Customer invoices and credit notes**: the same PDF the customer receives
  when the document is sent. The stored one when it exists; otherwise it is
  rendered with the report the invoice sending flow would use, without
  storing anything on the invoice.
* **Vendor bills and credit notes**: the PDF attached to the document (its
  main attachment when it is a PDF, otherwise its first PDF attachment). A
  vendor document without a PDF attached is left out.

Each file is named after the document (its number), with the characters
invalid in file names replaced; two files with the same name get a
" (2)" suffix instead of overwriting each other.

The behavior is the same in every sending flow of payments that send the
payment receipt report: the *Send receipt by email* button (composer, where
the user sees the documents before sending and can remove them), the mass
*Send receipts by email* action, automatic sending with a template (e.g.
the email of a receiptbook on posting) and scheduled messages.

When the attachments exceed the size limit of the outgoing mail server, the
composer shows a warning with the total and the limit. Nothing is removed:
the user decides.

With both settings off, emails are exactly the same as without this module.
