# -*- coding: utf-8 -*-
{
    'name': "Reporte de Flujos Proyectados",
    'summary': """
        Reporte financiero de flujos proyectados (Cash Flow) basado en 
        cuentas a cobrar y pagar.
    """,
    'author': "DevZinapsia",
    'category': 'Accounting/Accounting',
    'version': '1.0',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/projected_flows_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_items.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}