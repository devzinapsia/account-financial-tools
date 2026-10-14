{
    "name": "Mejoras a traducciones contables - Mayor de clientes",
    "version": "19.0.1.0.0",
    "summary": "Cobrar en el Mayor de Clientes de account_ux",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account_translation_improvements", "account_ux"],
    "data": [
        "data/account_ux_overrides.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": True,
}
