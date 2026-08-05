{
    "name": "Account Move Classification",
    "version": "19.0.1.0.0",
    "summary": "Classify invoices and journal entries with a color tag.",
    "author": "Zinapsia",
    "website": "https://github.com/devzinapsia/account-financial-tools",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "security/account_move_classification_rules.xml",
        "views/account_move_classification_views.xml",
        "views/account_move_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "account_move_classification/static/src/js/classification_badge_field.js",
            "account_move_classification/static/src/xml/classification_badge_field.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
