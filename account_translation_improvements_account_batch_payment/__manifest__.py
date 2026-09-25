{
    "name": "Mejoras a traducciones contables - Pagos por lotes",
    "version": "19.0.1.0.0",
    "summary": "Cobros por lotes en clientes",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account_translation_improvements", "account_batch_payment"],
    "data": [
        "data/account_batch_payment_overrides.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": True,
}
