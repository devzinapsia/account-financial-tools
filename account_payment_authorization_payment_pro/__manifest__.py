{
    "name": "Account Payment Authorization - Payment Pro",
    "version": "19.0.1.1.0",
    "summary": "Bridge account_payment_authorization with ingadhoc's account_payment_pro, "
    "so authorization schemes see the vendor bill a payment_pro draft payment is "
    "meant to settle.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account_payment_authorization", "account_payment_pro"],
    "data": [
        "views/account_payment_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
