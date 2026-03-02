# Copyright 2012 Therp BV (<http://therp.nl>)
# Copyright 2013-2018 BCIM SPRL (<http://www.bcim.be>)
# Copyright 2022 Simone Rubino - TAKOBI
# Copyright 2024-2025 Zinapsia (<https://github.com/devzinapsia>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Partner Financial Defaults",
    "version": "18.0.1.1.1",
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