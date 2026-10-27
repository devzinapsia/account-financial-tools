{
    "name": "Correos en copia en transacciones",
    "version": "19.0.1.2.0",
    "summary": "Agrega direcciones internas en copia visible (Cc) y oculta (Cco) "
    "a los correos de facturas, recibos, órdenes de pago, ventas y compras.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/mail_transaction_cc_security.xml",
        "data/mail_transaction_cc_type_data.xml",
        "views/mail_transaction_cc_rule_views.xml",
        "views/mail_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_transaction_cc/static/src/chatter/chatter_transaction_cc.js",
            "mail_transaction_cc/static/src/chatter/chatter_transaction_cc.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
