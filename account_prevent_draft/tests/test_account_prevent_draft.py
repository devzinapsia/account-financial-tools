from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ar.tests.common import TestArCommon


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestAccountPreventDraft(TestArCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.res_partner_adhoc
        # Testing environment without certificate: posting on a web service
        # journal runs l10n_ar_edi's local dummy validation (fills a CAE)
        # instead of connecting to ARCA.
        cls.company_ri.sudo().write({
            'l10n_ar_afip_ws_environment': 'testing',
            'l10n_ar_afip_ws_crt_id': False,
        })
        cls.journal_wsfe = cls._create_ar_journal('RAW_MAW', 11)
        cls.journal_wsfex = cls._create_ar_journal('FEEWS', 12)
        cls.journal_online = cls._create_ar_journal('RLI_RLM', 13)
        cls.journal_preprinted = cls._create_ar_journal('II_IM', 14)

    @classmethod
    def _create_ar_journal(cls, pos_system, pos_number):
        return cls.env['account.journal'].create({
            'name': 'Sales %s' % pos_system,
            'type': 'sale',
            'code': 'T%s' % pos_number,
            'company_id': cls.company_ri.id,
            'l10n_latam_use_documents': True,
            'l10n_ar_afip_pos_system': pos_system,
            'l10n_ar_afip_pos_number': pos_number,
            'l10n_ar_afip_pos_partner_id': cls.partner_ri.id,
        })

    def _create_posted_move(self, journal, move_type='out_invoice', cae=None):
        move = self._create_invoice_ar(journal_id=journal, move_type=move_type)
        move.action_post()
        self.assertEqual(move.state, 'posted')
        if cae:
            # Simulates a CAE obtained outside Odoo and loaded manually.
            move.l10n_ar_afip_auth_code = cae
        return move

    def test_web_service_invoice_with_cae_is_blocked(self):
        for journal in (self.journal_wsfe, self.journal_wsfex):
            with self.subTest(journal=journal.l10n_ar_afip_pos_system):
                self.assertTrue(journal.l10n_ar_afip_ws)
                move = self._create_posted_move(journal)
                # Posting without ARCA certificates runs the local dummy
                # validation, which fills the CAE like a real web service.
                self.assertTrue(move.l10n_ar_afip_auth_code)
                with self.assertRaises(ValidationError):
                    move.button_draft()
                self.assertEqual(move.state, 'posted')

    def test_web_service_credit_note_with_cae_is_blocked(self):
        move = self._create_posted_move(self.journal_wsfe, move_type='out_refund')
        self.assertTrue(move.l10n_ar_afip_auth_code)
        with self.assertRaises(ValidationError):
            move.button_draft()
        self.assertEqual(move.state, 'posted')

    def test_web_service_invoice_without_cae_is_not_blocked(self):
        move = self._create_posted_move(self.journal_wsfe)
        move.l10n_ar_afip_auth_code = False
        move.button_draft()
        self.assertEqual(move.state, 'draft')

    def test_non_web_service_invoice_with_manual_cae_is_not_blocked(self):
        for journal in (self.journal_online, self.journal_preprinted):
            with self.subTest(journal=journal.l10n_ar_afip_pos_system):
                self.assertFalse(journal.l10n_ar_afip_ws)
                move = self._create_posted_move(journal, cae='75123456789012')
                move.button_draft()
                self.assertEqual(move.state, 'draft')

    def test_non_web_service_credit_note_with_manual_cae_is_not_blocked(self):
        move = self._create_posted_move(self.journal_online, move_type='out_refund', cae='75123456789012')
        move.button_draft()
        self.assertEqual(move.state, 'draft')
