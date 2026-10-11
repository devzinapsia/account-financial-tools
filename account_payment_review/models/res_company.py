from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    payment_review_enabled = fields.Boolean(
        string="Payment review",
        default=True,
        help="Vendor payments confirmed from now on enter the review "
        "circuit as 'Pending review', unless an exemption below applies.",
    )
    payment_review_min_amount = fields.Monetary(
        string="Review from amount",
        currency_field="currency_id",
        help="Vendor payments below this amount, in company currency, don't "
        "require review. Leave it at 0 to review payments of any amount.",
    )
    payment_review_exempt_domain = fields.Char(
        string="Payments that don't require review",
        default="[]",
        help="Vendor payments matching these conditions don't require "
        "review, e.g. a petty cash journal. Leave it empty to apply no "
        "exemption.",
    )
    payment_review_answer_days = fields.Integer(
        string="Days to answer observations",
        default=3,
        help="Deadline of the activity assigned to the issuer of a payment "
        "when the reviewer records observations on it.",
    )
