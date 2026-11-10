=====================================================
Facturas adjuntas al enviar órdenes de pago y recibos
=====================================================

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

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Settings**, section **Payment emails**
(per company; each payment uses the settings of its own company):

* **Attach invoices when sending a payment order** (*Adjuntar comprobantes
  de facturas al enviar una orden de pago*): applies to outgoing payments.
* **Attach invoices when sending a receipt** (*Adjuntar comprobantes de
  facturas al enviar un recibo*): applies to incoming payments.
* **Journals whose invoices are not attached** (*Diarios cuyas facturas no
  se adjuntan*), visible when one of the settings above is on: sales and
  purchase journals of the company whose documents are never attached.
  Typically the document adjustment journals loaded by the Go Live, whose
  documents only carry the opening balances and are meaningless to the
  partner.

Size limit: emails are limited by the **Max Email Size** of the outgoing
mail server (*Settings ‣ Technical ‣ Email ‣ Outgoing Mail Servers*), or by
the system parameter ``base.default_max_email_size`` (in MB, 10 by default)
when the server has none. Above that limit Odoo itself replaces the
attachments of the email with download links in its body; the composer
warns about it before sending.

Vendor bills: attach the vendor's PDF to each bill (usually it already is,
when the bill is created from the PDF or from an incoming email). A bill
without a PDF is not attached.

Usage
=====

#. Open a posted payment order or receipt and click **Send receipt by
   email**.
#. The composer lists the payment receipt report (and, with
   ``l10n_ar_tax``, the withholding certificates) followed by the PDF of
   each invoice and credit note of the payment. Remove the ones you don't
   want to send, as with any other attachment.
#. If the attachments exceed the size limit of the mail server, a warning
   shows the total and the limit. Remove attachments, or send anyway: Odoo
   then replaces the attachments with download links in the email body.
#. Click **Send**.

The same documents are attached when the payments are sent from the list
view (*Actions ‣ Send receipts by email*), automatically with a template
(e.g. a receiptbook's email on posting) or as a scheduled message.

Coexistence with the ingadhoc modules:

* ``l10n_ar_tax``: its withholding certificates PDF stays attached exactly as
  before, before the documents.
* ``account_payment_pro``: install
  *Facturas adjuntas al enviar órdenes de pago y recibos - Payment Pro*
  (``account_payment_email_invoices_account_payment_pro``, installed
  automatically), so that payment bundles (``l10n_ar_payment_bundle``)
  attach the documents settled by their linked payments.

Bug Tracker
===========

Bugs are tracked on
`GitHub Issues <https://github.com/devzinapsia/account-financial-tools/issues>`_.
In case of trouble, please check there if your issue has already been
reported.

Credits
=======

Authors
-------

* Zinapsia

Maintainers
-----------

This module is maintained by Zinapsia.

This module is part of the
`account-financial-tools <https://github.com/devzinapsia/account-financial-tools>`_
project.
