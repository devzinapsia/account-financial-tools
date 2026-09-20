Go to **Accounting ‣ Configuration ‣ Chart of Accounts**, open an
expense account, and set its **Tags** field to one of *Bienes*,
*Servicios*, *Locaciones* or *Bienes de Uso*, depending on what that
account is used for. Only one of these 4 tags can be set on the same
account at a time.

Accounts without any of these tags still get a Concepto from the
purchase line's product (if any), or default to Concepto 3 (Servicio)
if there is neither a tag nor a product - see the module description
for the full priority order.
