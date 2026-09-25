from lxml import etree

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

PAY_IDS = ("account_invoice_payment_btn", "account_invoice_payment_secondary_btn")
COLLECT_IDS = ("account_invoice_collect_btn", "account_invoice_collect_secondary_btn")
CUSTOMER_TYPES = ("out_invoice", "out_refund", "out_receipt")
VENDOR_TYPES = ("in_invoice", "in_refund", "in_receipt")


@tagged("post_install", "-at_install")
class TestAccountTranslationImprovementsSurcharge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user = new_test_user(
            cls.env,
            login="ati_sur_accountant",
            groups="base.group_user,account.group_account_manager",
        )
        view = cls.env.ref("account.view_move_form")
        arch = cls.env["account.move"].with_user(user).get_view(view.id, "form")["arch"]
        cls.form = etree.fromstring(arch)

    def _button(self, button_id):
        buttons = self.form.xpath("//button[@id='%s']" % button_id)
        self.assertEqual(len(buttons), 1, button_id)
        return buttons[0]

    def _visible_buttons(self, move_type, state, has_outstanding):
        values = {
            "state": state,
            "payment_state": "not_paid",
            "move_type": move_type,
            "invoice_has_outstanding": has_outstanding,
            "authorized_transaction_ids": False,
        }
        return [
            self._button(button_id).get("string")
            for button_id in PAY_IDS + COLLECT_IDS
            if not safe_eval(self._button(button_id).get("invisible"), values)
        ]

    def test_collect_buttons_follow_surcharge(self):
        """The "Collect" buttons get the same method and context as the
        surcharge module's "Pay" buttons."""
        for button_id in PAY_IDS + COLLECT_IDS:
            button = self._button(button_id)
            self.assertEqual(button.get("name"), "action_force_register_payment", button_id)
            self.assertEqual(
                safe_eval(button.get("context")), {"open_invoice_payment": True}, button_id
            )

    def test_one_button_per_move_type(self):
        # Draft included: the surcharge module allows paying draft invoices
        for state in ("draft", "posted"):
            for has_outstanding in (False, True):
                for move_type in CUSTOMER_TYPES:
                    self.assertEqual(
                        self._visible_buttons(move_type, state, has_outstanding), ["Collect"]
                    )
                for move_type in VENDOR_TYPES:
                    self.assertEqual(
                        self._visible_buttons(move_type, state, has_outstanding), ["Pay"]
                    )
                self.assertEqual(self._visible_buttons("entry", state, has_outstanding), [])

    def test_cancelled_shows_nothing(self):
        for move_type in CUSTOMER_TYPES + VENDOR_TYPES:
            self.assertEqual(self._visible_buttons(move_type, "cancel", False), [])
