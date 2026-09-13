from odoo import fields, models


class AccountBankStatementUnlinkWizard(models.TransientModel):
    _name = 'account.bank.statement.unlink.wizard'
    _description = "Confirm deleting bank statement(s) with reconciled lines"

    statement_ids = fields.Many2many('account.bank.statement', string="Statements to delete", required=True)

    def action_confirm_unlink(self):
        self.ensure_one()
        self.statement_ids.with_context(statement_unlink_confirmed=True).unlink()
