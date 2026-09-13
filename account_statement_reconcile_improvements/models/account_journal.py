from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Snapshot of the last successful bank statement file import for this
    # journal: column mapping (by header name, so it survives column reordering)
    # plus the format options (encoding, separator, decimal/thousand separator,
    # sheet, ...) that base_import's own base_import.mapping doesn't cover,
    # since that model is keyed only by res_model (global across all journals/
    # banks), not per journal. See tools note in wizard/base_import_import.py.
    bank_statement_import_profile = fields.Json(
        string="Bank Statement Import Profile",
        copy=False,
        help="Technical field: last successful import settings (column "
             "mapping and file format options) for this journal, used to "
             "prefill the bank statement import wizard next time.",
    )
