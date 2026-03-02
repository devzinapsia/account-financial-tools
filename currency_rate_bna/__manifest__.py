{
    'name': 'Currency Rate BNA (Argentina)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Update currency rates from Banco Nación Argentina',
    'description': """
        Este módulo permite obtener las tasas de cambio de divisas
        desde el Banco de la Nación Argentina (BNA).
        
        Características:
        - Obtiene cotización del dólar estadounidense (USD)
        - Se integra con el sistema de tasas automáticas de Odoo
        - Usa la cotización de Divisas (no Billetes)
    """,
    'author': 'Zinapsia',
    'website': 'https://www.zinapsia.com',
    'license': 'LGPL-3',
    'depends': [
        'currency_rate_live',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'external_dependencies': {
        'python': ['requests', 'bs4'],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}