from odoo import fields, models


class AccountBankStatementUnlinkWizard(models.TransientModel):
    _name = 'account.bank.statement.unlink.wizard'
    _description = "Confirm deleting bank statement(s) with reconciled lines"

    statement_ids = fields.Many2many('account.bank.statement', string="Statements to delete", required=True)

    def action_confirm_unlink(self):
        self.ensure_one()
        self.statement_ids.with_context(statement_unlink_confirmed=True).unlink()
        # This wizard is reached through a RedirectWarning raised from inside
        # the original unlink() call, not through a normal button click on
        # the list/form view - the web client has no onClose callback wired
        # up to refresh that origin view once this dialog closes, so the
        # deleted statement (and its now-detached lines, in whatever view the
        # user was on) would otherwise keep showing until a manual refresh.
        return {'type': 'ir.actions.client', 'tag': 'reload'}
