from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, UserError


class AccountBankStatement(models.Model):
    # mail.thread is added so the chatter actually stores/shows messages -
    # the native form view (account_accountant.view_bank_statement_form_bank_rec_widget)
    # already has a <chatter/> widget, but it silently renders empty without
    # this mixin. Used to post the rejected-duplicate-rows table on import.
    _inherit = ['account.bank.statement', 'mail.thread']

    import_file_hash = fields.Char(
        string="Import File Hash",
        index=True,
        copy=False,
        help="SHA-256 of the source file used to import this statement, "
             "used to block re-importing the exact same file for the same "
             "journal. Empty for statements not created by a file import.",
    )

    # NULLs never conflict with each other in a Postgres unique index, so
    # statements without a hash (created manually, or by OCR) are unaffected.
    # This is a defense-in-depth safety net: the user-facing rejection with a
    # friendly message happens earlier, in create().
    _import_file_hash_uniq = models.Constraint(
        'unique (journal_id, import_file_hash)',
        "This bank statement file was already imported for this journal.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            import_file_hash = vals.get('import_file_hash')
            if not import_file_hash:
                continue
            journal_id = vals.get('journal_id') or self.env.context.get('default_journal_id')
            if not journal_id:
                continue
            duplicate = self.search([
                ('journal_id', '=', journal_id),
                ('import_file_hash', '=', import_file_hash),
            ], limit=1)
            if duplicate:
                raise UserError(self.env._(
                    "This file was already imported for this journal as "
                    "statement %(name)s, on %(date)s by %(user)s. Import "
                    "blocked to avoid duplicating transactions.",
                    name=duplicate.name or duplicate.reference or duplicate.id,
                    date=duplicate.create_date,
                    user=duplicate.create_uid.name,
                ))
        return super().create(vals_list)

    def unlink(self):
        if not self.env.context.get('statement_unlink_confirmed'):
            reconciled_lines = self.line_ids.filtered('is_reconciled')
            if reconciled_lines:
                action = self.env.ref(
                    'account_statement_reconcile_improvements'
                    '.action_account_bank_statement_unlink_wizard'
                ).id
                raise RedirectWarning(
                    self.env._(
                        "Deleting %(count)s statement(s) will unreconcile and "
                        "delete %(lines)s reconciled statement line(s), "
                        "reopening their matched invoices/payments as "
                        "pending. This cannot be undone.",
                        count=len(self),
                        lines=len(reconciled_lines),
                    ),
                    action,
                    self.env._("Review and confirm"),
                    {'default_statement_ids': [(6, 0, self.ids)]},
                )
        # The warning above was already shown (or explicitly bypassed via
        # context) at this point: unreconcile blindly, restoring the matched
        # invoices/payments to their pending state, then let the normal
        # account.bank.statement.line.unlink() cascade delete the lines.
        for statement in self:
            reconciled_lines = statement.line_ids.filtered('is_reconciled')
            reconciled_lines.line_ids.remove_move_reconcile()
        return super().unlink()
