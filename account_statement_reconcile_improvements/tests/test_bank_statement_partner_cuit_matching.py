from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestBankStatementPartnerCuitMatching(AccountTestInvoicingCommon):

    def test_child_contacts_are_excluded_keeping_the_parent_company(self):
        """Odoo copies a company's VAT to its own child contacts: a company
        with 3 contacts sharing the same CUIT must resolve to the parent,
        not fail because 4 records share the VAT.
        """
        company = self.env['res.partner'].create({
            'name': 'Acme SA',
            'is_company': True,
            'vat': '20123456786',
        })
        for i in range(3):
            self.env['res.partner'].create({
                'name': f'Acme Contact {i}',
                'parent_id': company.id,
                'vat': '20123456786',
            })
        found = self.env['res.partner']._find_unique_partner_by_cuit('20123456786')
        self.assertEqual(found, company)

    def test_two_parent_companies_sharing_a_cuit_keeps_the_oldest(self):
        older = self.env['res.partner'].create({'name': 'Older Co', 'vat': '20123456786'})
        newer = self.env['res.partner'].create({'name': 'Newer Co', 'vat': '20123456786'})
        # Force a deterministic create_date ordering regardless of test run speed.
        self.env.cr.execute(
            "UPDATE res_partner SET create_date = create_date - interval '1 day' WHERE id = %s",
            (older.id,),
        )
        found = self.env['res.partner']._find_unique_partner_by_cuit('20123456786')
        self.assertEqual(found, older)

    def test_no_match_returns_empty_recordset(self):
        found = self.env['res.partner']._find_unique_partner_by_cuit('20123456786')
        self.assertFalse(found)

    def test_vat_stored_with_dashes_still_matches_normalized_cuit(self):
        company = self.env['res.partner'].create({'name': 'Acme SA', 'vat': '20-12345678-6'})
        found = self.env['res.partner']._find_unique_partner_by_cuit('20123456786')
        self.assertEqual(found, company)
