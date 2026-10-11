{
    "name": "Revisión de órdenes de pago",
    "version": "19.0.1.0.0",
    "summary": "Control interno posterior de los pagos a proveedores ya confirmados: "
    "un revisor los firma como revisados o deja observaciones que el emisor responde.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account", "mail"],
    "data": [
        "security/account_payment_review_security.xml",
        "security/ir.model.access.csv",
        "data/mail_message_subtype_data.xml",
        "data/mail_activity_type_data.xml",
        "views/account_payment_views.xml",
        "views/res_config_settings_views.xml",
        "wizards/account_payment_review_wizard_views.xml",
        "wizards/account_payment_review_answer_wizard_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "account_payment_review/static/src/js/review_badge_char_field.js",
            "account_payment_review/static/src/xml/review_badge_char_field.xml",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
