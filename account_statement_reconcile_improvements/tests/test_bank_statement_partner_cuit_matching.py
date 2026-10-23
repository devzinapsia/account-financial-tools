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

    def test_own_company_cuit_is_never_matched(self):
        """A client's own CUIT routinely shows up in a bank statement's
        free-text legend (most commonly on a transfer between the
        client's own bank accounts) - matching it would assign the
        company's own res.partner as the line's contact, which is never a
        correct result and breaks every feature that filters by contact
        afterwards (see models/res_partner.py's own docstring).
        """
        self.env.company.partner_id.vat = '20123456786'
        found = self.env['res.partner']._find_unique_partner_by_cuit('20123456786')
        self.assertFalse(found, "The active company's own CUIT must never resolve to a contact")

    def test_another_companys_own_cuit_is_also_never_matched(self):
        """The exclusion isn't scoped to just the currently active
        company - a group's own inter-company transfers can carry any of
        its other companies' CUITs just as easily.
        """
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        other_company.partner_id.vat = '20123456786'
        found = self.env['res.partner']._find_unique_partner_by_cuit('20123456786')
        self.assertFalse(found, "No company's own CUIT, active or not, must ever resolve to a contact")
