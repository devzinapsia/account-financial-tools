{
    "name": "Mejoras al ajuste por inflación",
    "version": "19.0.1.3.0",
    "summary": "Varios asientos de cierre/apertura, primer ejercicio en Odoo y simulación con detalle por cuenta en el ajuste por inflación",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Localizations",
    "depends": ["l10n_ar_account_reports"],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "data": [
        "report/inflation_adjustment_report.xml",
        "views/inflation_adjustment_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
