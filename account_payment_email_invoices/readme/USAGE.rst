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
