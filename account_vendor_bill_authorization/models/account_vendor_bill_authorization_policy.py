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
        default=lambda self: str(
            [
                ("move_type", "in", ["in_invoice", "in_refund"]),
                ("state", "=", "draft"),
            ]
        ),
        help="Conditions a vendor bill or vendor credit/debit note must meet "
        "(logical AND) to match this policy, evaluated against "
        "account.move fields -- e.g. the classification "
        "(classification_id), the vendor, the journal, or the total amount, "
        "e.g. to build amount tiers with several policies. An empty domain "
        "matches any vendor bill or vendor credit/debit note (catch-all "
        "policy). The Type and Status conditions match what this module "
        "only ever actually evaluates against (draft vendor bills and "
        "vendor credit/debit notes), so they keep the record count shown "
        "while editing this domain accurate -- remove them if you really "
        "want to build a domain that reads as broader than that.",
    )
    always_block = fields.Boolean(
        string="Always block",
        help="If checked, a vendor bill matching this policy can never be "
        "confirmed nor approved by anyone, regardless of the Authorizers "
        "field (which is ignored in that case) and regardless of any other "
        "matching policy. Use this to explicitly and permanently deny a "
        "category of vendor bills, e.g. bills without a classification.",
    )
    authorized_user_ids = fields.Many2many(
        "res.users",
        string="Authorizers",
        help="Users allowed to approve a vendor bill matching this policy. "
        "Ignored if 'Always block' is checked. If left empty (and "
        "'Always block' is not checked), any vendor bill matching this "
        "policy can never be approved either -- this has the same practical "
        "effect as 'Always block', but leaving the box unchecked here "
        "usually means it was left empty by mistake rather than on "
        "purpose.",
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
