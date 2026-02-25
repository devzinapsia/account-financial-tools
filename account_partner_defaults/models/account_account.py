# Copyright 2012 Therp BV (<http://therp.nl>)
# Copyright 2013-2018 BCIM SPRL (<http://www.bcim.be>)
# Copyright 2022 Simone Rubino - TAKOBI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    expense_partner_ids = fields.Many2many(
        'res.partner',
        string='Expense Associated Partners',
        compute='_compute_associated_partners',
        store=False,
        help="Partners that have this account as their default expense account"
    )
    
    income_partner_ids = fields.Many2many(
        'res.partner',
        string='Income Associated Partners',
        compute='_compute_associated_partners', 
        store=False,
        help="Partners that have this account as their default income account"
    )
    
    expense_partner_names = fields.Char(
        string='Expense Partners',
        compute='_compute_partner_names',
        help="Names of partners using this as expense account"
    )
    
    income_partner_names = fields.Char(
        string='Income Partners', 
        compute='_compute_partner_names',
        help="Names of partners using this as income account"
    )

    def _compute_associated_partners(self):
        """Compute partners that use this account as default expense/income"""
        for account in self:
            # Find partners that have this account as expense account
            expense_partners = self.env['res.partner'].search([
                ('property_account_expense', '=', account.id)
            ])
            
            # Find partners that have this account as income account  
            income_partners = self.env['res.partner'].search([
                ('property_account_income', '=', account.id)
            ])
            
            account.expense_partner_ids = expense_partners
            account.income_partner_ids = income_partners

    @api.depends('expense_partner_ids', 'income_partner_ids')
    def _compute_partner_names(self):
        """Compute string representation of partner names"""
        for account in self:
            expense_names = ', '.join(account.expense_partner_ids.mapped('name'))
            income_names = ', '.join(account.income_partner_ids.mapped('name'))
            
            account.expense_partner_names = expense_names or 'None'
            account.income_partner_names = income_names or 'None'

