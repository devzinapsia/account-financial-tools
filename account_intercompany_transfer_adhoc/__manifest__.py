{
    "name": "Transferencias intercompany - Banco y Caja de adhoc",
    "version": "19.0.1.0.0",
    "summary": "Muestra las transferencias intercompany en el menú Banco y Caja de las "
    "transferencias internas de adhoc.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account_intercompany_transfer", "account_internal_transfer"],
    "data": [
        "views/menus.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": True,
}
