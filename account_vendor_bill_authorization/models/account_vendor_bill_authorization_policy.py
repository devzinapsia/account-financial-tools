from odoo import fields, models
from odoo.tools.safe_eval import safe_eval


class AccountVendorBillAuthorizationPolicy(models.Model):
    _name = "account.vendor.bill.authorization.policy"
    _description = "Vendor Bill Authorization Policy"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        help="Leave empty to make this policy apply to all companies.",
    )
    domain = fields.Char(
        string="Conditions",
        default=lambda self: str([("move_type", "in", ["in_invoice", "in_refund"])]),
        help="Conditions a vendor bill or vendor credit/debit note must meet "
        "(logical AND) to match this policy, evaluated against "
        "account.move fields when the bill is confirmed -- e.g. the "
        "classification (classification_id), the vendor, the journal, or the "
        "total amount, e.g. to build amount tiers with several policies. An "
        "empty domain matches any vendor bill or vendor credit/debit note "
        "(catch-all policy). The Type condition matches what this module "
        "only ever actually evaluates against, so it keeps the record count "
        "shown while editing this domain accurate. Don't add a condition on "
        "the Status: policies are evaluated while the bill is being "
        "confirmed.",
    )
    always_block = fields.Boolean(
        string="Always block",
        help="If checked, a vendor bill matching this policy can never be "
        "confirmed by anyone, regardless of the Authorizers field (which is "
        "ignored in that case) and regardless of any other matching policy. "
        "Use this to explicitly and permanently deny a category of vendor "
        "bills, e.g. bills without a classification.",
    )
    authorized_user_ids = fields.Many2many(
        "res.users",
        string="Authorizers",
        help="Users allowed to authorize the payment of a confirmed vendor "
        "bill matching this policy. Ignored if 'Always block' is checked. "
        "If left empty (and 'Always block' is not checked), any vendor bill "
        "matching this policy can never be authorized, nor paid, either -- "
        "leaving it empty usually means it was left empty by mistake rather "
        "than on purpose.",
    )

    def _matches_bill(self, move):
        """Return True if this policy's domain matches ``move``. An empty
        domain matches any vendor bill (catch-all policy).
        """
        self.ensure_one()
        if self.company_id and self.company_id != move.company_id:
            return False
        domain = safe_eval(self.domain or "[]")
        return bool(move.filtered_domain(domain))
