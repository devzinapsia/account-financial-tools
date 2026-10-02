{
    "name": "Autorización de facturas de proveedor - Excepción por pago directo",
    "version": "19.0.1.0.0",
    "summary": "Las facturas de proveedor pagadas en la carga con un diario de pago "
    "directo habilitado (p. ej. Fondo Fijo) no requieren autorización.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": [
        "account_vendor_bill_authorization",
        "account_payment_pro",
        "account_journal_security",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
