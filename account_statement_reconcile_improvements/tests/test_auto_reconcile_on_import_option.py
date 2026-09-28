from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAutoReconcileOnImportOption(AccountTestInvoicingCommon):
    """The 'Automatically reconcile when contact, date and amount match'
    checkbox in the import screen (default on, remembered per journal)
    controls whether a real import calls
    action_auto_reconcile_unassigned_by_amount_and_date() on the
    just-imported lines.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _create_open_invoice(self, amount=100.0, date='2026-01-01', partner=None):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': (partner or self.partner_a).id,
            'invoice_date': date,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': amount,
                'quantity': 1,
                'tax_ids': [(6, 0, [])],
            })],
        })
        invoice.action_post()
        return invoice

    def _create_wizard(self, csv_content):
        return self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': csv_content.encode(),
            'file_name': 'test_import.csv',
            'file_type': 'text/csv',
        })

    def _base_options(self, **extra):
        return {
            'has_headers': True,
            'bank_stmt_import': True,
            'quoting': '"',
            'separator': ',',
            'encoding': 'utf-8',
            **extra,
        }

    def test_auto_reconcile_runs_by_default_on_real_import(self):
        """The option defaults to on: a real import with a unique
        date+amount match (no partner involved) must reconcile it even
        when the wizard's own options dict doesn't mention the key at all -
        exactly how a real request from a journal that never configured
        this before would look.
        """
        self._create_open_invoice(amount=100.0, date='2026-01-01')
        wizard = self._create_wizard("Fecha,Importe\n2026-01-01,100.0\n")

        result = wizard.execute_import(
            fields=['date', 'amount'],
            columns=['Fecha', 'Importe'],
            options=self._base_options(),
            dryrun=False,
        )

        line = self.env['account.bank.statement.line'].browse(result['ids'])
        self.assertTrue(line.is_reconciled, "Auto-reconcile must run by default when the option is never mentioned")

    def test_auto_reconcile_matches_a_line_with_a_confirmed_contact(self):
        """The same on-import auto-reconcile must also pick up a line whose
        contact was already resolved during this same import - either via
        the CUIT-in-free-text match, or a column mapped directly to
        Contact.
        """
        self._create_open_invoice(amount=150.0, date='2026-02-01', partner=self.partner_a)
        wizard = self._create_wizard("Fecha,Importe,Contacto\n2026-02-01,150.0,%d\n" % self.partner_a.id)

        result = wizard.execute_import(
            fields=['date', 'amount', 'partner_id/.id'],
            columns=['Fecha', 'Importe', 'Contacto'],
            options=self._base_options(),
            dryrun=False,
        )

        line = self.env['account.bank.statement.line'].browse(result['ids'])
        self.assertTrue(line.is_reconciled, "A line with a confirmed contact must also be auto-reconciled")
        self.assertTrue(line.move_id.checked, "A match backed by an already-confirmed contact must not be flagged to check")

    def test_auto_reconcile_can_be_disabled(self):
        self._create_open_invoice(amount=100.0, date='2026-01-01')
        wizard = self._create_wizard("Fecha,Importe\n2026-01-01,100.0\n")

        result = wizard.execute_import(
            fields=['date', 'amount'],
            columns=['Fecha', 'Importe'],
            options=self._base_options(bank_stmt_auto_reconcile_by_contact_date_amount=False),
            dryrun=False,
        )

        line = self.env['account.bank.statement.line'].browse(result['ids'])
        self.assertFalse(line.is_reconciled, "Auto-reconcile must not run when explicitly disabled for this import")

    def test_auto_reconcile_option_is_saved_per_journal(self):
        wizard = self._create_wizard("Fecha,Importe\n2026-01-01,50.0\n")

        wizard.execute_import(
            fields=['date', 'amount'],
            columns=['Fecha', 'Importe'],
            options=self._base_options(bank_stmt_auto_reconcile_by_contact_date_amount=False),
            dryrun=False,
        )

        self.assertFalse(
            self.bank_journal.bank_statement_import_profile['options']['bank_stmt_auto_reconcile_by_contact_date_amount'],
            "The choice must be remembered on the journal's profile, same as the duplicate-lines option",
        )

    def test_parse_preview_defaults_to_true_when_nothing_was_ever_saved_for_the_journal(self):
        wizard = self._create_wizard("Fecha,Importe\n2026-01-01,50.0\n")

        preview = wizard.parse_preview(self._base_options())

        self.assertTrue(
            preview['options']['bank_stmt_auto_reconcile_by_contact_date_amount'],
            "Unlike the duplicate-lines checkbox, this one must default to checked",
        )

    def test_parse_preview_uses_the_saved_value_once_one_exists(self):
        wizard = self._create_wizard("Fecha,Importe\n2026-01-01,50.0\n")
        wizard._save_bank_statement_import_profile(
            self.bank_journal,
            columns=['Fecha', 'Importe'],
            fields=['date', 'amount'],
            options=self._base_options(bank_stmt_auto_reconcile_by_contact_date_amount=False),
        )

        preview = wizard.parse_preview(self._base_options())

        self.assertFalse(
            preview['options']['bank_stmt_auto_reconcile_by_contact_date_amount'],
            "A previously-saved False must win over the True default",
        )
