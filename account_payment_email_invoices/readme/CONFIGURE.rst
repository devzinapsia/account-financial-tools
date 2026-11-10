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
