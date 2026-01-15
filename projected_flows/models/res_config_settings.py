from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    projected_flow_initial_balance_ids = fields.Many2many(
        'account.account',
        string="Cuentas Saldo Inicial"
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        company = self.env.company

        res.update({
            'projected_flow_initial_balance_ids': company.projected_flow_initial_balance_ids
        })
        return res

    def set_values(self):
        super().set_values()
        company = self.env.company

        company.projected_flow_initial_balance_ids = [(6, 0, self.projected_flow_initial_balance_ids.ids)]