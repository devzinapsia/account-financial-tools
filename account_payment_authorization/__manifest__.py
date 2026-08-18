{
    "name": "Account Payment Authorization",
    "version": "19.0.1.0.13",
    "summary": "Require authorization from configured users before confirming "
    "vendor payments that match configurable policies.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account", "account_move_classification"],
    "data": [
        "security/ir.model.access.csv",
        "security/account_payment_authorization_security.xml",
        "views/account_payment_authorization_scheme_views.xml",
        "views/account_payment_views.xml",
        "wizards/account_payment_authorization_reject_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
