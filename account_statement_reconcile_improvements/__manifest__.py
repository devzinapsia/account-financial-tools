{
    "name": "Mejoras a conciliación bancaria",
    "version": "19.0.1.1.8",
    "summary": "Enhancements to the bank statement file import and reconciliation process.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": [
        "account_accountant",
        "account_bank_statement_import_csv",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_journal_dashboard_kanban_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/account_bank_statement_unlink_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
