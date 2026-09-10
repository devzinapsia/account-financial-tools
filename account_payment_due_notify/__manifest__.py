{
    "name": "Notificaciones de vencimientos de pago",
    "version": "19.0.1.1.1",
    "summary": "Notifica automáticamente a los usuarios configurados antes "
    "de que venzan comprobantes a pagar.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account"],
    "data": [
        "data/ir_cron_data.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
