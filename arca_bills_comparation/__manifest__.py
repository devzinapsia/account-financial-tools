{
    "name": "ARCA Bills Comparison",
    "version": "19.0.1.0.1",
    "summary": "Compare ARCA 'Mis Comprobantes Recibidos' exports against vendor bills in Odoo",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Localizations",
    "depends": [
        "account",
        "l10n_ar",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/arca_bill_comparison_line_views.xml",
        "views/arca_bill_comparison_batch_views.xml",
        "wizards/arca_bill_comparison_wizard_views.xml",
        "views/menu_items.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
