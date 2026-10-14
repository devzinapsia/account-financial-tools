import ast

from lxml import etree

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

from ..hooks import CONTEXT_KEY, uninstall_hook

CUSTOMERS = "account_ux.action_account_moves_customers_ledger"
VENDORS = "account_ux.action_account_moves_vendors_ledger"


@tagged("post_install", "-at_install")
class TestAccountTranslationImprovementsAccountUx(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="ati_ux_accountant",
            groups="base.group_user,account.group_account_manager,account.group_account_user",
        )

    def _context(self, xmlid):
        return ast.literal_eval(self.env.ref(xmlid).context)

    def _visible_buttons(self, xmlid):
        """Header buttons shown when the list is opened from ``xmlid``,
        evaluated like the web client does: the search model consumes the
        search_default_* keys and removes them from the context."""
        action = self.env.ref(xmlid)
        context = {
            key: value
            for key, value in self._context(xmlid).items()
            if not key.startswith("search_default_")
        }
        arch = self.env["account.move.line"].with_user(self.user).get_view(action.view_id.id, "list")["arch"]
        return [
            button.get("string")
            for button in etree.fromstring(arch).xpath(
                "//header/button[@name='action_payment_items_register_payment']"
            )
            if not safe_eval(button.get("invisible") or "False", {"context": context})
        ]

    def test_customers_ledger_context(self):
        context = self._context(CUSTOMERS)
        self.assertIs(context.get(CONTEXT_KEY), True)
        # account_ux's own keys are kept
        self.assertEqual(context.get("search_default_trade_receivable"), 1)
        self.assertNotIn(CONTEXT_KEY, self._context(VENDORS))

    def test_ledger_buttons(self):
        self.assertEqual(self._visible_buttons(CUSTOMERS), ["Collect"])
        self.assertEqual(self._visible_buttons(VENDORS), ["Pay"])

    def test_upgrade_is_idempotent(self):
        before = self._context(CUSTOMERS)
        self.env["ir.module.module"]._account_translation_improvements_account_ux_set_context()
        self.assertEqual(self._context(CUSTOMERS), before)

    def test_uninstall_hook_removes_key(self):
        before = self._context(CUSTOMERS)
        uninstall_hook(self.env)
        after = self._context(CUSTOMERS)
        self.assertNotIn(CONTEXT_KEY, after)
        before.pop(CONTEXT_KEY)
        self.assertEqual(after, before)
        self.assertEqual(self._visible_buttons(CUSTOMERS), ["Pay"])
