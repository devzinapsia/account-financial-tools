{
    "name": "Autorización de facturas de proveedor",
    "version": "19.0.1.0.0",
    "summary": "Requiere la autorización de usuarios configurados antes de confirmar "
    "facturas y notas de crédito/débito de proveedor que cumplan las políticas "
    "definidas.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account", "account_move_classification"],
    "data": [
        "security/ir.model.access.csv",
        "security/account_vendor_bill_authorization_security.xml",
        "views/account_vendor_bill_authorization_policy_views.xml",
        "views/account_move_views.xml",
        "wizards/account_vendor_bill_authorization_reject_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
