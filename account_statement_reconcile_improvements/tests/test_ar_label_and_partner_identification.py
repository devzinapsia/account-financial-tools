from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestArLabelAndPartnerIdentification(AccountTestInvoicingCommon):
    """The 'Label + Contact (CUIT in free-text legend)' virtual field is for
    banks (e.g. BBVA) whose single 'Concepto' column is both the
    transaction's own label AND the only place the CUIT shows up - unlike
    the plain 'Contact (CUIT in free-text legend)' field, mapping a column
    to this one keeps the original text as payment_ref instead of
    discarding it for the resolved partner_id.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']
        # Synthetic CUIT, same one used in test_bank_statement_partner_cuit_matching.py
        # and confirmed there to have zero pre-existing matches in this database -
        # a real CUIT (e.g. any starting with '307') risks colliding with actual
        # demo/client data already seeded in the local test DB.
        cls.partner_a.vat = '20123456786'

    def _create_wizard(self, csv_content):
        return self.env['base_import.import'].with_context(
            default_journal_id=self.bank_journal.id,
        ).create({
            'res_model': 'account.bank.statement.line',
            'file': csv_content.encode(),
            'file_name': 'test_import.csv',
            'file_type': 'text/csv',
        })

    def _base_options(self):
        return {
            'has_headers': True,
            'bank_stmt_import': True,
            'quoting': '"',
            'separator': ',',
            'encoding': 'utf-8',
        }

    def test_column_becomes_the_label_and_resolves_the_partner(self):
        wizard = self._create_wizard(
            "Fecha,Importe,Concepto\n2026-01-01,100.0,PAGO PROVEEDOR CUIT 20123456786\n"
        )
        result = wizard.execute_import(
            fields=['date', 'amount', 'x_ar_label_and_partner_identification'],
            columns=['Fecha', 'Importe', 'Concepto'],
            options=self._base_options(),
            dryrun=False,
        )
        line = self.env['account.bank.statement.line'].browse(result['ids'])
        self.assertEqual(line.payment_ref, 'PAGO PROVEEDOR CUIT 20123456786', "The column's own text must still become the label")
        self.assertEqual(line.partner_id, self.partner_a, "The same text must also resolve the partner by CUIT")

    def test_no_cuit_in_text_still_imports_the_label(self):
        wizard = self._create_wizard(
            "Fecha,Importe,Concepto\n2026-01-01,100.0,COMPRA VARIOS\n"
        )
        result = wizard.execute_import(
            fields=['date', 'amount', 'x_ar_label_and_partner_identification'],
            columns=['Fecha', 'Importe', 'Concepto'],
            options=self._base_options(),
            dryrun=False,
        )
        line = self.env['account.bank.statement.line'].browse(result['ids'])
        self.assertEqual(line.payment_ref, 'COMPRA VARIOS')
        self.assertFalse(line.partner_id)

    def test_explicit_partner_column_wins_but_label_is_still_kept(self):
        """When the user also maps a real Contact column, this field must
        not override that explicit choice with its own CUIT guess - same
        rule as the plain CUIT-only field - but it must still import the
        column's own text as the label, since that's the whole point of
        this field over the plain one.
        """
        other_partner = self.env['res.partner'].create({'name': 'Explicit Partner'})
        wizard = self._create_wizard(
            "Fecha,Importe,Concepto,Contacto\n2026-01-01,100.0,PAGO CUIT 20123456786,%d\n" % other_partner.id
        )
        result = wizard.execute_import(
            fields=['date', 'amount', 'x_ar_label_and_partner_identification', 'partner_id/.id'],
            columns=['Fecha', 'Importe', 'Concepto', 'Contacto'],
            options=self._base_options(),
            dryrun=False,
        )
        line = self.env['account.bank.statement.line'].browse(result['ids'])
        self.assertEqual(line.payment_ref, 'PAGO CUIT 20123456786', "The label must still be imported from its own column")
        self.assertEqual(line.partner_id, other_partner, "The explicitly mapped Contact column must win")

    def test_ambiguous_text_keeps_the_label_but_leaves_partner_blank(self):
        """extract_cuit() already returns None when more than one valid CUIT
        is found in the same text, regardless of whether any partner
        actually has those VAT numbers - this just confirms the label is
        still imported even when the partner guess is deliberately skipped.
        """
        wizard = self._create_wizard(
            "Fecha,Importe,Concepto\n2026-01-01,100.0,CUIT 20123456786 Y 20987654326\n"
        )
        result = wizard.execute_import(
            fields=['date', 'amount', 'x_ar_label_and_partner_identification'],
            columns=['Fecha', 'Importe', 'Concepto'],
            options=self._base_options(),
            dryrun=False,
        )
        line = self.env['account.bank.statement.line'].browse(result['ids'])
        self.assertEqual(line.payment_ref, 'CUIT 20123456786 Y 20987654326')
        self.assertFalse(line.partner_id, "More than one valid CUIT in the text must not guess a partner")
