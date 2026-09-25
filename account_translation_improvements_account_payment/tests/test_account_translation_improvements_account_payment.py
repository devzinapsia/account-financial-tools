from lxml import etree

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

BUTTON_IDS = (
    "account_invoice_payment_btn",
    "account_invoice_payment_secondary_btn",
    "account_invoice_collect_btn",
    "account_invoice_collect_secondary_btn",
)


@tagged("post_install", "-at_install")
class TestAccountTranslationImprovementsAccountPayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user = new_test_user(
            cls.env,
            login="ati_ap_accountant",
            groups="base.group_user,account.group_account_manager",
        )
        view = cls.env.ref("account.view_move_form")
        arch = cls.env["account.move"].with_user(user).get_view(view.id, "form")["arch"]
        cls.form = etree.fromstring(arch)

    def _visible_buttons(self, move_type, has_outstanding, authorized):
        values = {
            "state": "posted",
            "payment_state": "not_paid",
            "move_type": move_type,
            "invoice_has_outstanding": has_outstanding,
            "authorized_transaction_ids": authorized,
        }
        visible = []
        for button_id in BUTTON_IDS:
            button = self.form.xpath("//button[@id='%s']" % button_id)[0]
            if not safe_eval(button.get("invisible"), values):
                visible.append(button.get("string"))
        return visible

    def test_authorized_transaction_hides_both_labels(self):
        for has_outstanding in (False, True):
            for move_type, label in (
                ("out_invoice", "Collect"),
                ("out_refund", "Collect"),
                ("out_receipt", "Collect"),
                ("in_invoice", "Pay"),
                ("in_refund", "Pay"),
                ("in_receipt", "Pay"),
            ):
                self.assertEqual(
                    self._visible_buttons(move_type, has_outstanding, False), [label]
                )
                self.assertEqual(self._visible_buttons(move_type, has_outstanding, True), [])
