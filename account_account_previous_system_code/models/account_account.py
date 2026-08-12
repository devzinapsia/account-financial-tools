from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = "account.account"

    previous_system_account_code = fields.Char(
        string="Previous system account code",
        index=True,
        help="Code this account had in the system it was migrated from. "
        "Kept for reference (mappings, reconciliations, historical "
        "lookups).",
    )

    @api.constrains("previous_system_account_code")
    def _check_previous_system_account_code_unique(self):
        # Empty values are always allowed and never considered duplicates
        # of one another. Uniqueness is scoped per company, mirroring how
        # account.account._ensure_code_is_unique() scopes the "code" field:
        # accounts sharing a company (directly, or through a parent/child
        # company relationship) cannot reuse the same code.
        for account in self.sudo():
            code = account.previous_system_account_code
            if not code:
                continue
            for company in account.company_ids:
                duplicate = self.sudo().search(
                    [
                        ("previous_system_account_code", "=", code),
                        ("id", "!=", account.id),
                        "|",
                        ("company_ids", "parent_of", company.ids),
                        ("company_ids", "child_of", company.ids),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        _(
                            'The previous system account code "%(code)s" is '
                            'already used by account "%(account)s".',
                            code=code,
                            account=duplicate.display_name,
                        )
                    )
