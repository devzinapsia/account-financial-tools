from odoo import api, models

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.onchange('product_id', 'partner_id')
    def _onchange_partner_zinapsia_defaults(self):
        for line in self:
            if not line.product_id and line.display_type == 'product' and line.move_id.partner_id:
                partner = line.move_id.partner_id
                inv_type = line.move_id.move_type
                
                # Cuentas
                if inv_type in ('in_invoice', 'in_refund') and partner.property_account_expense:
                    line.account_id = partner.property_account_expense
                elif inv_type in ('out_invoice', 'out_refund') and partner.property_account_income:
                    line.account_id = partner.property_account_income

                # Impuestos
                taxes = partner.default_expense_tax_ids if inv_type in ('in_invoice', 'in_refund') else partner.default_income_tax_ids
                if taxes:
                    line.tax_ids = [(6, 0, taxes.ids)]

    @api.depends('product_id', 'partner_id')
    def _compute_account_id(self):
        super()._compute_account_id()
        for line in self:
            if not line.product_id and line.display_type == 'product' and line.move_id.partner_id:
                partner = line.move_id.partner_id
                acc = partner.property_account_expense if line.move_id.is_purchase_document() else partner.property_account_income
                if acc:
                    line.account_id = acc

    def _post(self, soft=True):
        """ Lógica de Autoguardado Senior al publicar la factura """
        for line in self:
            if not line.product_id and line.display_type == 'product' and line.move_id.partner_id:
                partner = line.move_id.partner_id
                if line.move_id.is_purchase_document() and partner.auto_update_account_expense:
                    if partner.property_account_expense != line.account_id:
                        partner.property_account_expense = line.account_id
                elif line.move_id.is_sale_document() and partner.auto_update_account_income:
                    if partner.property_account_income != line.account_id:
                        partner.property_account_income = line.account_id
        return super()._post(soft=soft)