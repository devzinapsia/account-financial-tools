from odoo import models


class AccountReconcileModel(models.Model):
    _inherit = 'account.reconcile.model'

    def _apply_reconcile_models(self, statement_lines):
        # EXTENDS account_accountant
        already_reconciled = statement_lines.filtered('is_reconciled')
        res = super()._apply_reconcile_models(statement_lines)
        newly_reconciled = statement_lines.filtered('is_reconciled') - already_reconciled
        newly_reconciled._flag_as_to_check_if_configured()
        return res
