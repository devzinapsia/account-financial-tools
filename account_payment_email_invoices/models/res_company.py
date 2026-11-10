from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Journal types whose documents (invoices, bills and credit notes) can be
# attached to a payment email.
INVOICE_JOURNAL_TYPES = ("sale", "purchase")


class ResCompany(models.Model):
    _inherit = "res.company"

    attach_invoices_on_payment_order = fields.Boolean(
        string="Attach invoices when sending a payment order",
        help="When a payment order is sent by email, also attach the PDF of the "
        "vendor bills and credit notes it settles (the PDF attached to each bill).",
    )
    attach_invoices_on_receipt = fields.Boolean(
        string="Attach invoices when sending a receipt",
        help="When a receipt is sent by email, also attach the PDF of the "
        "customer invoices and credit notes it settles (the same PDF the "
        "customer receives).",
    )
    no_attachment_journal_ids = fields.Many2many(
        "account.journal",
        relation="res_company_payment_email_no_attachment_journal_rel",
        column1="company_id",
        column2="journal_id",
        string="Journals whose invoices are not attached",
        domain=[("type", "in", INVOICE_JOURNAL_TYPES)],
        help="Example: document adjustment journals loaded by the Go Live.",
    )

    @api.constrains("no_attachment_journal_ids")
    def _check_no_attachment_journal_ids(self):
        for company in self:
            wrong = company.no_attachment_journal_ids.filtered(
                lambda j: j.company_id != company or j.type not in INVOICE_JOURNAL_TYPES
            )
            if wrong:
                raise ValidationError(
                    _(
                        "Only sales and purchase journals of company %(company)s can be "
                        "excluded from payment emails: %(journals)s.",
                        company=company.display_name,
                        journals=", ".join(wrong.mapped("display_name")),
                    )
                )
