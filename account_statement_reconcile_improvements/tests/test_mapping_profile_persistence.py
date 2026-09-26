from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestMappingProfilePersistence(AccountTestInvoicingCommon):
    """3.1: the per-journal column mapping saved after a successful import
    must be honored in full on the next one - including a column the user
    deliberately left unmapped, not just the ones they mapped to a field.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _create_wizard(self):
        return self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': b'Fecha,Importe,Ref\n2026-01-01,100.0,ABC\n',
            'file_name': 'test_import.csv',
            'file_type': 'text/csv',
        })

    def test_explicitly_unmapped_column_is_remembered_as_unmapped(self):
        """Regression test: a column intentionally left unmapped ('Don't
        import') used to be silently omitted from the saved profile instead
        of being recorded as an explicit non-mapping - indistinguishable
        from a column that was simply never seen before, so it fell back to
        whatever the native fuzzy-match guessed on the next import instead
        of staying unmapped.
        """
        wizard = self._create_wizard()
        wizard._save_bank_statement_import_profile(
            self.bank_journal,
            columns=['Fecha', 'Importe', 'Ref'],
            fields=['date', 'amount', False],
            options={'has_headers': True},
        )
        fields_tree = wizard.get_fields_tree('account.bank.statement.line')
        headers = ['Fecha', 'Importe', 'Ref']
        suggestions = wizard._get_mapping_suggestions(
            headers=headers,
            header_types={(index, header): [] for index, header in enumerate(headers)},
            fields_tree=fields_tree,
        )
        ref_suggestions = {key: value for key, value in suggestions.items() if key[1] == 'Ref'}
        self.assertFalse(
            ref_suggestions,
            f"'Ref' was explicitly left unmapped last time, it must not get a suggestion: {ref_suggestions}",
        )

    def test_mapped_column_is_remembered(self):
        wizard = self._create_wizard()
        wizard._save_bank_statement_import_profile(
            self.bank_journal,
            columns=['Fecha', 'Importe', 'Ref'],
            fields=['date', 'amount', 'payment_ref'],
            options={'has_headers': True},
        )
        fields_tree = wizard.get_fields_tree('account.bank.statement.line')
        headers = ['Fecha', 'Importe', 'Ref']
        suggestions = wizard._get_mapping_suggestions(
            headers=headers,
            header_types={(index, header): [] for index, header in enumerate(headers)},
            fields_tree=fields_tree,
        )
        ref_suggestions = {key: value for key, value in suggestions.items() if key[1] == 'Ref'}
        self.assertTrue(ref_suggestions, "Expected a remembered suggestion for 'Ref'")
        self.assertEqual(next(iter(ref_suggestions.values()))['field_path'], ['payment_ref'])

    def test_force_duplicate_lines_choice_is_remembered_per_journal(self):
        """The import screen's 'Import even if rows look like duplicates'
        checkbox doesn't exist client-side until it's toggled at least once
        in the current session (it's lazily created, see
        static/src/js/force_duplicate_lines_option.js) - so on a fresh
        wizard for a journal that already had it enabled once, parse_preview
        must inject the remembered value into `options` itself, the same
        channel the client already uses to prefill format options like
        'separator'/'encoding'.
        """
        wizard = self._create_wizard()
        wizard._save_bank_statement_import_profile(
            self.bank_journal,
            columns=['Fecha', 'Importe'],
            fields=['date', 'amount'],
            options={'has_headers': True, 'bank_stmt_force_duplicate_lines': True},
        )
        self.assertTrue(
            self.bank_journal.bank_statement_import_profile['options'].get('bank_stmt_force_duplicate_lines'),
            "The choice should have been saved on the journal's profile",
        )

        options = {'has_headers': True, 'separator': ',', 'quoting': '"', 'encoding': 'utf-8'}
        wizard.parse_preview(options)
        self.assertTrue(
            options.get('bank_stmt_force_duplicate_lines'),
            "parse_preview() should have injected the remembered value into options",
        )

    def test_force_duplicate_lines_is_not_overridden_once_set_by_the_client(self):
        """A value the client already sent this session (the user toggled
        the checkbox themselves) must never be overwritten by an older
        saved default - only missing keys get the remembered value filled
        in.
        """
        wizard = self._create_wizard()
        wizard._save_bank_statement_import_profile(
            self.bank_journal,
            columns=['Fecha', 'Importe'],
            fields=['date', 'amount'],
            options={'has_headers': True, 'bank_stmt_force_duplicate_lines': True},
        )
        options = {
            'has_headers': True, 'separator': ',', 'quoting': '"', 'encoding': 'utf-8',
            'bank_stmt_force_duplicate_lines': False,
        }
        wizard.parse_preview(options)
        self.assertFalse(options.get('bank_stmt_force_duplicate_lines'))
