from odoo import api, fields, models


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
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        compute="_compute_currency_id",
        store=True,
        readonly=True,
    )
    classification_id = fields.Many2one(
        "account.move.classification",
        string="Invoice classification",
        help="Leave empty to match any classification (or none at all).",
    )
    partner_ids = fields.Many2many(
        "res.partner",
        string="Vendors",
        domain="[('supplier_rank', '>', 0)]",
        help="Leave empty to match any vendor.",
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment method",
        domain="[('payment_type', '=', 'outbound')]",
        help="Leave empty to match any payment method.",
    )
    amount_min = fields.Monetary(
        string="Minimum amount",
        help="Leave empty to not filter by amount. When set, the scheme "
        "matches payments whose amount is greater than or equal to this "
        "value.",
    )
    authorized_user_ids = fields.Many2many(
        "res.users",
        string="Authorized users",
        help="Users allowed to approve a payment matching this scheme. If "
        "left empty, any payment matching this scheme can never be "
        "approved.",
    )

    @api.depends("company_id")
    def _compute_currency_id(self):
        for scheme in self:
            scheme.currency_id = (
                scheme.company_id.currency_id or self.env.company.currency_id
            )

    def _matches_payment(self, payment):
        """Return True if all the non-empty conditions of this scheme are
        satisfied by ``payment`` (logical AND). A scheme with every filter
        field empty matches any vendor payment (catch-all scheme).
        """
        self.ensure_one()
        if self.company_id and self.company_id != payment.company_id:
            return False
        if (
            self.classification_id
            and self.classification_id != payment.authorization_invoice_id.classification_id
        ):
            return False
        if self.partner_ids and payment.partner_id not in self.partner_ids:
            return False
        if (
            self.payment_method_line_id
            and self.payment_method_line_id != payment.payment_method_line_id
        ):
            return False
        if self.amount_min and payment.amount < self.amount_min:
            return False
        return True
