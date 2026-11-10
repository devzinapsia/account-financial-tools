from odoo import fields, models

from .res_company import INVOICE_JOURNAL_TYPES


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    attach_invoices_on_payment_order = fields.Boolean(
        related="company_id.attach_invoices_on_payment_order",
        readonly=False,
    )
    attach_invoices_on_receipt = fields.Boolean(
        related="company_id.attach_invoices_on_receipt",
        readonly=False,
    )
    # A related field does not inherit the target field's domain: repeat it
    # here, scoped to the settings' company.
    no_attachment_journal_ids = fields.Many2many(
        related="company_id.no_attachment_journal_ids",
        readonly=False,
        domain="[('company_id', '=', company_id), ('type', 'in', %s)]" % (INVOICE_JOURNAL_TYPES,),
    )
