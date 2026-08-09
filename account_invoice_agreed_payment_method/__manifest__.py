{
    "name": "Account Invoice Agreed Payment Method",
    "version": "19.0.1.0.4",
    "summary": "Register the payment method agreed with the vendor on vendor bills.",
    "author": "Zinapsia",
    "website": "https://github.com/devzinapsia/account-financial-tools",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "data/account_move_agreed_payment_method_data.xml",
        "views/account_move_agreed_payment_method_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
