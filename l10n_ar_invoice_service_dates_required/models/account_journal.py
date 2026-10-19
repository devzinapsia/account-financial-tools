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
    l10n_ar_service_period_default = fields.Selection(
        selection=[
            ("empty", "Empty"),
            ("invoice_month", "Invoice month"),
            ("invoice_day", "Invoice day"),
        ],
        string="Default service period",
        default="invoice_month",
        required=True,
        help="Service billing period proposed on electronic invoices of this "
        "journal with an ARCA concept of Services or Products and Services:\n"
        "- Empty: nothing is proposed, the user enters the dates.\n"
        "- Invoice month: first to last day of the invoice date's month.\n"
        "- Invoice day: the invoice date itself, as both start and end.\n"
        "If the dates are still empty when the invoice is confirmed, they are "
        "filled in with the invoice day when that option is selected, or with "
        "the invoice month otherwise, since ARCA requires them.",
    )
    l10n_ar_service_period_print = fields.Boolean(
        string="Print service period on documents",
        default=True,
        help="When disabled, the invoiced period is not printed on the "
        "electronic invoices of this journal with an ARCA concept of "
        "Services or Products and Services.",
    )
