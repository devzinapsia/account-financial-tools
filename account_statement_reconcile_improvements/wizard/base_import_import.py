import hashlib
import unicodedata

from odoo import _, models
from odoo.addons.base_import.models.base_import import FIELDS_RECURSION_LIMIT

from ..tools.ar_id_extraction import extract_cuit

# Virtual field offered in the mapping UI (alongside the native 'balance',
# 'debit', 'credit' synthetic fields added by account_bank_statement_import_csv)
# for the bank's free-text legend column, from which we extract a CUIT and
# resolve it to a partner - see res.partner._find_unique_partner_by_cuit().
_AR_IDENTIFICATION_FIELD = 'x_ar_partner_identification'

# Row shape heuristics used to find where the real header row starts in
# files that have leading metadata/title rows before it (e.g. BBVA exports).
_HEADER_DATE_KEYWORDS = ('fecha',)
_HEADER_OTHER_KEYWORDS = (
    'importe', 'saldo', 'debito', 'credito', 'concepto', 'descripcion',
    'detalle', 'comprobante',
)
_HEADER_DETECTION_MAX_LOOKAHEAD = 20

# Format options worth remembering per journal - the ones base_import.mapping
# itself never persists at all (it only remembers column->field pairs, and
# only globally by res_model, not per journal - see docstring on
# _get_mapping_suggestions below).
_PROFILE_OPTION_KEYS = (
    'encoding', 'separator', 'quoting', 'sheet',
    'date_format', 'datetime_format',
    'float_thousand_separator', 'float_decimal_separator',
)


def _normalize_header_cell(value):
    text = str(value or '')
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return text.strip().lower()


class Base_ImportImport(models.TransientModel):
    _inherit = 'base_import.import'

    # -------------------------------------------------------------------
    # 3.5/3.6/3.7 - CUIT/DNI virtual mapping field
    # -------------------------------------------------------------------
    def get_fields_tree(self, model, depth=FIELDS_RECURSION_LIMIT):
        fields_list = super().get_fields_tree(model, depth=depth)
        if model == 'account.bank.statement.line' and self.env.context.get('bank_stmt_import'):
            fields_list.append({
                'id': _AR_IDENTIFICATION_FIELD,
                'name': _AR_IDENTIFICATION_FIELD,
                'string': _("Contact (CUIT in free-text legend)"),
                'required': False,
                'fields': [],
                'type': 'char',
                'model_name': model,
            })
        return fields_list

    # -------------------------------------------------------------------
    # 3.9 - detect and drop leading junk rows / blank rows before the header
    # -------------------------------------------------------------------
    def _read_file(self, options):
        file_length, data_rows = super()._read_file(options)
        if self.res_model != 'account.bank.statement.line' or not options.get('has_headers'):
            return file_length, data_rows

        data_rows = [row for row in data_rows if any(cell not in (None, '') for cell in row)]
        header_row_index = self._detect_bank_statement_header_row(data_rows)
        if header_row_index:
            data_rows = data_rows[header_row_index:]
        return len(data_rows), data_rows

    def _detect_bank_statement_header_row(self, data_rows):
        """Return the index of the first row that looks like the real
        column-title row of a bank statement export, so that leading
        metadata/title/blank rows (e.g. account/period info on BBVA
        exports) are discarded automatically. Falls back to 0 (no rows
        discarded) when nothing in the lookahead window looks like a
        header - i.e. it never makes an already-correct file worse.
        """
        for index, row in enumerate(data_rows[:_HEADER_DETECTION_MAX_LOOKAHEAD]):
            normalized_cells = [_normalize_header_cell(cell) for cell in row]
            has_date_kw = any(
                keyword in cell for cell in normalized_cells for keyword in _HEADER_DATE_KEYWORDS
            )
            has_other_kw = any(
                keyword in cell for cell in normalized_cells for keyword in _HEADER_OTHER_KEYWORDS
            )
            if has_date_kw and has_other_kw:
                return index
        return 0

    # -------------------------------------------------------------------
    # 3.1 - per-journal mapping persistence
    #
    # base_import.mapping (native) only remembers column_name -> field_name
    # pairs, globally by res_model - not scoped by journal at all. Since
    # 'account.bank.statement.line' is shared by every bank, two journals
    # whose export happens to use the same header text for different
    # meanings silently stomp each other's saved mapping. This is the
    # actual root cause behind "sometimes Odoo forgets the mapping for a
    # given journal" - format options (encoding, separator, ...) are
    # already reliably auto-detected from the file on every import and are
    # not the issue.
    # -------------------------------------------------------------------
    def _get_bank_stmt_import_journal(self):
        if self.res_model != 'account.bank.statement.line':
            return self.env['account.journal']
        journal_id = self.env.context.get('default_journal_id')
        return self.env['account.journal'].browse(journal_id) if journal_id else self.env['account.journal']

    def _get_mapping_suggestions(self, headers, header_types, fields_tree):
        suggestions = super()._get_mapping_suggestions(headers, header_types, fields_tree)
        journal = self._get_bank_stmt_import_journal()
        saved_mapping = (journal.bank_statement_import_profile or {}).get('mapping') if journal else None
        if not saved_mapping:
            return suggestions
        for key, header in list(suggestions.keys()):
            field_name = saved_mapping.get(header)
            if field_name:
                suggestions[(key, header)] = {'field_path': [field_name], 'distance': 0}
        return suggestions

    # -------------------------------------------------------------------
    # 3.3, 3.4, 3.5/3.6/3.7 - hash, duplicate lines, CUIT->partner
    # -------------------------------------------------------------------
    def _parse_import_data(self, data, import_fields, options):
        # EXTENDS account_bank_statement_import_csv
        data = super()._parse_import_data(data, import_fields, options)
        if not options.get('bank_stmt_import'):
            return data

        if self.file:
            statement_vals = options.setdefault('statement_vals', {})
            statement_vals['import_file_hash'] = hashlib.sha256(self.file).hexdigest()

        data = self._resolve_ar_partner_identification(data, import_fields)
        data = self._filter_out_duplicate_lines(data, import_fields, options)
        return data

    def _resolve_ar_partner_identification(self, data, import_fields):
        if _AR_IDENTIFICATION_FIELD not in import_fields:
            return data
        legend_index = import_fields.index(_AR_IDENTIFICATION_FIELD)

        if 'partner_id' in import_fields or 'partner_id/.id' in import_fields:
            # The user explicitly mapped a partner column too: don't override
            # their explicit choice with our own CUIT-based guess.
            import_fields.pop(legend_index)
            for row in data:
                row.pop(legend_index)
            return data

        partner_model = self.env['res.partner']
        import_fields[legend_index] = 'partner_id/.id'
        for row in data:
            cuit = extract_cuit(row[legend_index])
            partner = partner_model._find_unique_partner_by_cuit(cuit) if cuit else partner_model.browse()
            row[legend_index] = partner.id or False
        return data

    def _filter_out_duplicate_lines(self, data, import_fields, options):
        """3.4: skip (by default) rows that look like a movement already
        present for this journal - same date, partner and amount, per the
        section 2 "same movement" heuristic - regardless of which statement
        or reconciliation state that existing line has. This intentionally
        does not offer a per-row checkbox in the preview grid (that would
        require rebuilding base_import's preview table component); instead
        duplicates are excluded automatically and reported as a warning.
        Pass options['bank_stmt_force_duplicate_lines'] = True to disable
        this check entirely for one import.
        """
        if options.get('bank_stmt_force_duplicate_lines'):
            return data
        journal = self._get_bank_stmt_import_journal()
        if not journal or 'date' not in import_fields or 'amount' not in import_fields:
            return data

        date_index = import_fields.index('date')
        amount_index = import_fields.index('amount')
        # Only trust a partner value we resolved ourselves (a real database
        # id from the CUIT match): a plainly-mapped 'partner_id' column is
        # still raw text/external-id at this pipeline stage (many2one
        # resolution happens later, in model.load()), so it can't be
        # compared against the field directly here.
        partner_index = import_fields.index('partner_id/.id') if 'partner_id/.id' in import_fields else None

        StatementLine = self.env['account.bank.statement.line']
        precision = journal.currency_id.decimal_places
        kept_rows = []
        duplicate_count = 0
        for row in data:
            try:
                date_value = row[date_index]
                amount_value = round(float(row[amount_index] or 0.0), precision)
                partner_value = row[partner_index] if partner_index is not None else False
                existing = StatementLine.search([
                    ('journal_id', '=', journal.id),
                    ('date', '=', date_value),
                    ('partner_id', '=', partner_value or False),
                ])
                is_duplicate = any(round(line.amount, precision) == amount_value for line in existing)
            except (TypeError, ValueError):
                # Never silently drop a row because our own dedup check
                # choked on an unexpected value shape - worst case it just
                # doesn't get flagged as a probable duplicate.
                is_duplicate = False
            if is_duplicate:
                duplicate_count += 1
                continue
            kept_rows.append(row)

        if duplicate_count:
            self._bank_stmt_duplicate_lines_skipped = duplicate_count
        return kept_rows

    # -------------------------------------------------------------------
    # 3.1 (save), 3.2, 3.7 (to_check tail)
    # -------------------------------------------------------------------
    def execute_import(self, fields, columns, options, dryrun=False):
        res = super().execute_import(fields, columns, options, dryrun=dryrun)

        duplicate_count = getattr(self, '_bank_stmt_duplicate_lines_skipped', 0)
        if duplicate_count:
            res.setdefault('messages', []).append({
                'type': 'warning',
                'message': _(
                    "%(count)s row(s) were not imported: they match an "
                    "existing statement line for this journal on the same "
                    "date, partner and amount (probable duplicate). Re-run "
                    "with the duplicate-lines check disabled if you are "
                    "sure they are not.",
                    count=duplicate_count,
                ),
                'record': False,
            })

        if dryrun or not options.get('bank_stmt_import') or not res.get('ids'):
            return res

        journal = self._get_bank_stmt_import_journal()
        lines = self.env['account.bank.statement.line'].browse(res['ids'])
        statements = lines.statement_id

        self._save_bank_statement_import_profile(journal, columns, fields, options)
        self._attach_import_file(statements)
        lines.filtered('is_reconciled')._flag_as_to_check_if_configured()
        return res

    def _save_bank_statement_import_profile(self, journal, columns, fields, options):
        if not journal or not options.get('has_headers'):
            return
        mapping = {
            column_name: field_name
            for column_name, field_name in zip(columns, fields)
            if column_name and field_name
        }
        if not mapping:
            return
        journal.bank_statement_import_profile = {
            'mapping': mapping,
            'options': {key: options[key] for key in _PROFILE_OPTION_KEYS if options.get(key)},
        }

    def _attach_import_file(self, statements):
        if not self.file:
            return
        for statement in statements:
            if statement.attachment_ids:
                continue
            self.env['ir.attachment'].create({
                'name': self.file_name or _("Bank statement import file"),
                'raw': self.file,
                'res_model': 'account.bank.statement',
                'res_id': statement.id,
            })
