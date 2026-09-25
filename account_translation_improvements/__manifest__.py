{
    "name": "Mejoras a traducciones contables",
    "version": "19.0.1.0.0",
    "summary": "Cobrar/Cobros en clientes y Notas de crédito en proveedores",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account"],
    "data": [
        "views/account_move_views.xml",
        "data/account_overrides.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
