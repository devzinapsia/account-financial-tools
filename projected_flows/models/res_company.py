from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    projected_flow_initial_balance_ids = fields.Many2many(
        comodel_name='account.account',
        relation='projected_flow_initial_balance_rel',
        column1='company_id',
        column2='account_id',
        string='Cuentas Saldo Inicial'
    )