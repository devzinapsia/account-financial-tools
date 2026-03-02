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
        'partner_expense_tax_rel',
        'partner_id',
        'tax_id',
        string='Impuestos de Compras por Defecto',
        # Filtramos para que solo muestre impuestos de compra
        domain=[('type_tax_use', '=', 'purchase')]
    )
    default_income_tax_ids = fields.Many2many(
        'account.tax',
        'partner_income_tax_rel',
        'partner_id',
        'tax_id',
        string='Impuestos de Ventas por Defecto',
        # Filtramos para que solo muestre impuestos de venta
        domain=[('type_tax_use', '=', 'sale')]
    )
    auto_update_account_expense = fields.Boolean(
        string="Autoguardar cuenta de gastos",
        default=False
    )
    auto_update_account_income = fields.Boolean(
        string="Autoguardar cuenta de ingresos",
        default=False
    )