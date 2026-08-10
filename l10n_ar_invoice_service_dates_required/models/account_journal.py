from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ar_service_period_dates_required = fields.Boolean(
        string="Validate ARCA service period date entry",
        default=False,
        help="When enabled, sales invoices posted through this journal with "
        "an ARCA concept of Services or Products and Services must have "
        "the service billing period (start/end dates) filled in.",
    )
