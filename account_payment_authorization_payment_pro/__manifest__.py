{
    "name": "Autorización de pagos a proveedores - Payment Pro",
    "version": "19.0.1.1.5",
    "summary": "Integra la autorización de pagos con account_payment_pro de ingadhoc, "
    "para que las políticas vean la factura que paga un borrador de pago "
    "creado desde ese flujo.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account_payment_authorization", "account_payment_pro"],
    "data": [
        "views/account_payment_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
