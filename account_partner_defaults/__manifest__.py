{
    "name": "Partner Financial Defaults",
    "version": "18.0.1.1.2",
    "summary": """
        Define cuentas, impuestos y glosas por defecto para partners.
        Optimizable para Odoo 18 y 19.
    """,
    "description": """
        Este módulo extiende la funcionalidad de los contactos para permitir:
        - Cuentas de ingresos/gastos predeterminadas.
        - Automatización de cuentas en facturas.
        - (Próximamente) Impuestos y leyendas por defecto.
    """,
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting",
    "depends": [
        "account",
        "l10n_ar",
        "base_address_extended", # Agregamos esto para asegurar que el campo exista
    ],
    "data": [
        "views/res_partner.xml",
        "views/account_account.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}