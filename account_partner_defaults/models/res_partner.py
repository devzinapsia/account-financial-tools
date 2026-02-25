from odoo import fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    property_account_income = fields.Many2one(
        'account.account', 
        company_dependent=True,
        string="Cuenta de Ingresos (Zinapsia)",
    )
    property_account_expense = fields.Many2one(
        'account.account', 
        company_dependent=True,
        string="Cuenta de Gastos (Zinapsia)",
    )
    default_expense_tax_ids = fields.Many2many(
        'account.tax', 
        'partner_default_expense_tax_rel',
        'partner_id', 'tax_id',
        string="Impuestos de Compra por Defecto"
    )
    default_income_tax_ids = fields.Many2many(
        'account.tax', 
        'partner_default_income_tax_rel',
        'partner_id', 'tax_id',
        string="Impuestos de Venta por Defecto"
    )
    auto_update_account_expense = fields.Boolean(
        string="Autoguardar cuenta de gastos",
        default=False
    )
    auto_update_account_income = fields.Boolean(
        string="Autoguardar cuenta de ingresos",
        default=False
    )