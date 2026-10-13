from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .account_intercompany_transfer import SEQUENCE_CODE

# Liquidity, receivable/payable, P&L and equity accounts are excluded: the
# bridge account must stay out of bank balances, aged balances and the debt
# a payment can settle. Same types core allows for outstanding accounts.
BRIDGE_ACCOUNT_TYPES = ("asset_current", "liability_current")


class ResCompany(models.Model):
    _inherit = "res.company"

    intercompany_transfer_account_id = fields.Many2one(
        "account.account",
        string="Intercompany transfer bridge account",
        check_company=True,
        domain=[("account_type", "in", BRIDGE_ACCOUNT_TYPES)],
        help="Counterpart of the payments created by intercompany transfers "
        "sent or received by this company. Its ledger grouped by partner shows "
        "the balance with each of the other companies.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._create_intercompany_transfer_sequences()
        return companies

    def _create_intercompany_transfer_sequences(self):
        """One numbering per company, drawn by the origin company of each
        transfer. Created here (install and company creation) rather than on
        the fly: only administrators may create sequences, and transfers
        must never need elevated rights. sudo() only creates this technical
        sequence for a company that is being set up.
        """
        sequences = self.env["ir.sequence"].sudo()
        existing = sequences.search([("code", "=", SEQUENCE_CODE), ("company_id", "in", self.ids)])
        missing = self - existing.company_id
        sequences.create(
            [
                {
                    "name": _("Intercompany transfers (%(company)s)", company=company.name),
                    "code": SEQUENCE_CODE,
                    "company_id": company.id,
                    # range_year is the year of the transfer date; plain
                    # year would be the year the number is drawn.
                    "prefix": "ICT/%(range_year)s/",
                    "padding": 5,
                    "use_date_range": True,
                    # A transfer that fails is rolled back entirely, its
                    # number included: no gaps in the numbering.
                    "implementation": "no_gap",
                }
                for company in missing
            ]
        )

    @api.constrains("intercompany_transfer_account_id")
    def _check_intercompany_transfer_account_id(self):
        for company in self.filtered("intercompany_transfer_account_id"):
            account = company.intercompany_transfer_account_id
            if not account.filtered_domain(self.env["account.account"]._check_company_domain(company)):
                raise ValidationError(
                    _(
                        "The intercompany transfer bridge account %(account)s does not belong to %(company)s.",
                        account=account.display_name,
                        company=company.display_name,
                    )
                )
            if not account.active:
                raise ValidationError(
                    _(
                        "The intercompany transfer bridge account %(account)s is archived.",
                        account=account.display_name,
                    )
                )
            if account.account_type not in BRIDGE_ACCOUNT_TYPES:
                raise ValidationError(
                    _(
                        "The intercompany transfer bridge account %(account)s must be a current asset "
                        "or a current liability account.",
                        account=account.display_name,
                    )
                )
            # Odoo identifies the liquidity line of a payment by the
            # outstanding accounts of its journal: a shared account would
            # turn the counterpart line into a liquidity line.
            method_line = self.env["account.payment.method.line"].search(
                [
                    ("payment_account_id", "=", account.id),
                    ("journal_id.company_id", "=", company.id),
                ],
                limit=1,
            )
            if method_line:
                raise ValidationError(
                    _(
                        "The intercompany transfer bridge account %(account)s is the outstanding account "
                        "of the payment method %(method)s of the journal %(journal)s. Use a dedicated account.",
                        account=account.display_name,
                        method=method_line.name,
                        journal=method_line.journal_id.display_name,
                    )
                )
