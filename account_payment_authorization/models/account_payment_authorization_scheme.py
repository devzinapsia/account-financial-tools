from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class AccountPaymentAuthorizationScheme(models.Model):
    _name = "account.payment.authorization.scheme"
    _description = "Payment Authorization Scheme"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        help="Leave empty to make this scheme apply to all companies.",
    )
    domain = fields.Char(
        string="Conditions",
        default="[]",
        help="Conditions a payment must meet (logical AND) to match this "
        "scheme, evaluated against account.payment fields -- including the "
        "linked vendor bill via authorization_invoice_id, e.g. "
        "authorization_invoice_id.classification_id, and the amount, e.g. "
        "to build amount tiers with several schemes. An empty domain "
        "matches any vendor payment (catch-all scheme).",
    )
    block_payment = fields.Boolean(
        string="Always block",
        help="If checked, a payment matching this scheme can never be "
        "approved by anyone, regardless of the Authorized users field "
        "(which is ignored in that case). Use this to explicitly and "
        "permanently deny a category of payments, e.g. vendor bills "
        "without a classification.",
    )
    authorized_user_ids = fields.Many2many(
        "res.users",
        string="Authorized users",
        help="Users allowed to approve a payment matching this scheme. "
        "Ignored if 'Always block' is checked. If left empty (and "
        "'Always block' is not checked), any payment matching this scheme "
        "can never be approved either -- this has the same practical "
        "effect as 'Always block', but leaving the box unchecked here "
        "usually means it was left empty by mistake rather than on "
        "purpose.",
    )

    def _matches_payment(self, payment):
        """Return True if this scheme's domain matches ``payment``. An
        empty domain matches any vendor payment (catch-all scheme).
        """
        self.ensure_one()
        if self.company_id and self.company_id != payment.company_id:
            return False
        domain = safe_eval(self.domain or "[]")
        return bool(payment.filtered_domain(domain))
