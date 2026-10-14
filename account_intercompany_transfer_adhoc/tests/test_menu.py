from odoo.tests import TransactionCase, tagged

from .. import uninstall_hook


@tagged("post_install", "-at_install")
class TestIntercompanyTransferAdhocMenu(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.menu = cls.env.ref("account_intercompany_transfer.menu_account_intercompany_transfer")
        cls.bank_and_cash = cls.env.ref("account_internal_transfer.menu_finance_bank_and_cash")
        cls.adhoc_transfers = cls.env.ref("account_internal_transfer.menu_action_account_payments_transfer")

    def test_menu_in_bank_and_cash(self):
        self.assertEqual(self.menu.parent_id, self.bank_and_cash)
        siblings = self.bank_and_cash.child_id.sorted(lambda menu: (menu.sequence, menu.id))
        position = list(siblings).index(self.menu)
        self.assertEqual(
            siblings[position - 1],
            self.adhoc_transfers,
            "Intercompany transfers come right after ingadhoc's Transfers.",
        )

    def test_menu_keeps_its_group(self):
        self.assertEqual(
            self.menu.group_ids,
            self.env.ref("account_intercompany_transfer.group_intercompany_transfer_user"),
        )

    def test_uninstall_hook_restores_the_menu(self):
        uninstall_hook(self.env)
        self.assertEqual(self.menu.parent_id, self.env.ref("account.account_transactions_menu"))
        self.assertEqual(self.menu.sequence, 32)
        # Nothing of ours is left under ingadhoc's menu, so it can be deleted.
        self.assertNotIn(self.menu, self.bank_and_cash.child_id)
