{
    "name": "Facturas adjuntas al enviar órdenes de pago y recibos",
    "version": "19.0.1.0.0",
    "summary": "Al enviar por correo una orden de pago o un recibo, adjunta también "
    "el PDF de las facturas y notas de crédito que intervienen en el pago.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": [
        "account",
        "mail",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/mail_compose_message_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
