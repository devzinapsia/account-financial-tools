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

    def _t(self, source, **kwargs):
        """Translate using the current user's own saved language
        preference (res.users.lang), not whatever 'lang' happens to be in
        this environment's context.

        create() is reached from the import wizard's execute_import(),
        which base_import's own JS calls via orm.silent (see
        @base_import/import_model.js _callImport) instead of a plain
        orm.call() - unlike the latter, it does not forward the session's
        user_context, so self.env.context['lang'] is empty for that call
        regardless of the user's language setting, and self.env._() renders
        in English no matter what. Forcing 'lang' from the user's own field
        (a plain read, unaffected by the request's context) sidesteps that
        entirely.
        """
        return self.with_context(lang=self.env.user.lang).env._(source, **kwargs)

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
                raise UserError(self._t(
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
                    self._t(
                        "Deleting %(count)s statement(s) will unreconcile and "
                        "delete %(lines)s reconciled statement line(s), "
                        "reopening their matched invoices/payments as "
                        "pending. This cannot be undone.",
                        count=len(self),
                        lines=len(reconciled_lines),
                    ),
                    action,
                    self._t("Review and confirm"),
                    {'default_statement_ids': [(6, 0, self.ids)]},
                )
        # The warning above was already shown (or explicitly bypassed via
        # context) at this point: unreconcile blindly, restoring the matched
        # invoices/payments to their pending state. account.bank.statement's
        # own statement_id field has no ondelete='cascade' (a plain
        # Many2one), so deleting the statement alone only detaches its lines
        # (statement_id becomes False) instead of removing them - explicitly
        # unlink the lines too, which is what actually deletes their
        # underlying account.move (account.bank.statement.line.unlink()
        # handles that part).
        #
        # Order matters: account.bank.statement.line._check_allow_unlink()
        # refuses to delete a line while its statement_id still points to a
        # valid/complete statement - so the lines must be captured now but
        # only unlinked *after* the statement itself is gone (which is what
        # clears statement_id on them).
        all_lines = self.line_ids
        for statement in self:
            reconciled_lines = statement.line_ids.filtered('is_reconciled')
            reconciled_lines.line_ids.remove_move_reconcile()
        result = super().unlink()
        all_lines.unlink()
        return result
