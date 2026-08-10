{
    "name": "L10n AR Invoice Service Dates Required",
    "version": "19.0.1.0.1",
    "summary": "Require the ARCA service billing period on electronic sales "
    "journals configured to enforce it.",
    "author": "Zinapsia",
    "website": "https://www.zinapsia.com",
    "license": "AGPL-3",
    "category": "Accounting/Localizations",
    "depends": ["account", "l10n_ar"],
    "data": [
        "views/account_journal_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
