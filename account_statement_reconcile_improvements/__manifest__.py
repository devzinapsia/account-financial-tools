{
    "name": "Mejoras a conciliación bancaria",
    "version": "19.0.1.0.0",
    "summary": "Enhancements to the bank statement file import and reconciliation process.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": [
        "account_accountant",
        "account_bank_statement_import_csv",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "wizard/account_bank_statement_unlink_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "account_statement_reconcile_improvements/static/src/js/*.js",
            "account_statement_reconcile_improvements/static/src/xml/*.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
