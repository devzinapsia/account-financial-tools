from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _mail_transaction_cc_filter_records(self):
        """The companies' own partners are never a customer or vendor
        communication."""
        company_partners = self.env["res.company"].sudo().search([]).partner_id
        return super()._mail_transaction_cc_filter_records().filtered(
            lambda partner: partner.commercial_partner_id not in company_partners
        )
