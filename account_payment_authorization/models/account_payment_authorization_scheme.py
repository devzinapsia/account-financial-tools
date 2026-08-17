from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class AccountPaymentAuthorizationScheme(models.Model):
    _name = "account.payment.authorization.scheme"
    _description = "Payment Authorization Policy"
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
                ("payment_type", "=", "outbound"),
                ("partner_type", "=", "supplier"),
                ("is_pending_confirmation", "=", True),
            ]
        ),
        help="Conditions a payment must meet (logical AND) to match this "
        "policy, evaluated against account.payment fields -- including the "
        "linked vendor bill via Invoices, e.g. "
        "invoice_ids.classification_id, and the amount, e.g. to build "
        "amount tiers with several policies. An empty domain matches any "
        "vendor payment (catch-all policy). The Payment type and Recipient "
        "type conditions match what this module only ever actually "
        "evaluates against (outbound vendor payments), so they keep the "
        "record count shown while editing this domain accurate -- remove "
        "them if you really want to build a domain that reads as broader "
        "than that. Prefer the Pending confirmation field over the "
        "payment's own Status when a condition needs to target payments "
        "still awaiting confirmation; see that field's own help text.",
    )
    block_payment = fields.Boolean(
        string="Always block",
        help="If checked, a payment matching this policy can never be "
        "approved by anyone, regardless of the Authorizers field "
        "(which is ignored in that case). Use this to explicitly and "
        "permanently deny a category of payments, e.g. vendor bills "
        "without a classification.",
    )
    authorized_user_ids = fields.Many2many(
        "res.users",
        string="Authorizers",
        help="Users allowed to approve a payment matching this policy. "
        "Ignored if 'Always block' is checked. If left empty (and "
        "'Always block' is not checked), any payment matching this policy "
        "can never be approved either -- this has the same practical "
        "effect as 'Always block', but leaving the box unchecked here "
        "usually means it was left empty by mistake rather than on "
        "purpose.",
    )

    def _matches_payment(self, payment):
        """Return True if this policy's domain matches ``payment``. An
        empty domain matches any vendor payment (catch-all policy).
        """
        self.ensure_one()
        if self.company_id and self.company_id != payment.company_id:
            return False
        domain = safe_eval(self.domain or "[]")
        return bool(payment.filtered_domain(domain))
