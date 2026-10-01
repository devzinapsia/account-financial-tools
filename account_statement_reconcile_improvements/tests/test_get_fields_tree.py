from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestGetFieldsTree(AccountTestInvoicingCommon):
    """account.bank.statement.line is unified with account.move (delegation
    inheritance since v17), which carries its own one2many field back to
    account.bank.statement.line (`statement_line_ids`). base_import's own
    field-tree builder recurses into one2many fields, so without a depth
    guard the two CUIT virtual fields below would get appended again on
    every one of those self-recursive calls too - surfacing as a confusing,
    non-functional duplicate nested under "Estados de cuenta /" in the
    mapping picker.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']

    def _virtual_field_occurrences(self, tree, path=""):
        hits = []
        for field in tree:
            if field['id'] in ('x_ar_partner_identification', 'x_ar_label_and_partner_identification'):
                hits.append(f"{path}/{field['id']}")
            if field.get('fields'):
                hits.extend(self._virtual_field_occurrences(field['fields'], f"{path}/{field['id']}"))
        return hits

    def test_virtual_fields_appear_only_once_at_the_top_level(self):
        wizard = self.env['base_import.import'].with_context(
            bank_stmt_import=True,
            default_journal_id=self.bank_journal.id,
        ).create({'res_model': 'account.bank.statement.line'})

        tree = wizard.get_fields_tree('account.bank.statement.line')

        self.assertEqual(
            self._virtual_field_occurrences(tree),
            ['/x_ar_partner_identification', '/x_ar_label_and_partner_identification'],
            "The CUIT virtual fields must appear exactly once, at the top level - "
            "not nested under 'Estados de cuenta' (statement_line_ids self-recursion)",
        )
