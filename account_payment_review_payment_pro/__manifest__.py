{
    "name": "Revisión de órdenes de pago - Payment Pro",
    "version": "19.0.1.0.0",
    "summary": "Integra la revisión de órdenes de pago con account_payment_pro de ingadhoc: "
    "el importe mínimo a revisar se compara contra el total de la orden de pago, "
    "incluidas retenciones.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account_payment_review", "account_payment_pro"],
    "data": [
        "wizards/account_payment_review_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
