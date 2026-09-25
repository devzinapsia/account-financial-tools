from lxml import etree

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

from ..hooks import uninstall_hook

CUSTOMER_TYPES = ("out_invoice", "out_refund", "out_receipt")
VENDOR_TYPES = ("in_invoice", "in_refund", "in_receipt")

# xmlid: (en_US, es_AR) expected while the module is installed
RENAMED = {
    "account.action_move_force_register_payment": ("Pay / Collect", "Pagar / Cobrar"),
    "account.menu_action_account_payments_receivable": ("Collections", "Cobros"),
    "account.action_account_payments": ("Customer Collections", "Cobros de clientes"),
    "account.menu_action_move_in_refund_type": ("Credit Notes", "Notas de crédito"),
    "account.action_move_in_refund_type": ("Credit Notes", "Notas de crédito"),
}


@tagged("post_install", "-at_install")
class TestAccountTranslationImprovements(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.env["res.lang"]._get_data(code="es_AR"):
            # Activating a language loads every module's terms in dependency
            # order, so this module's names win over account's ones.
            cls.env["res.lang"]._activate_lang("es_AR")
            cls.env["ir.module.module"].search(
                [("name", "in", ("account", "account_translation_improvements"))]
            )._update_translations("es_AR")
        cls.user = new_test_user(
            cls.env,
            login="ati_accountant",
            groups="base.group_user,account.group_account_manager",
        )
        cls.Move = cls.env["account.move"].with_user(cls.user)

    def _arch(self, view_xmlid, view_type, lang="en_US"):
        view = self.env.ref(view_xmlid)
        arch = self.Move.with_context(lang=lang).get_view(view.id, view_type)["arch"]
        return etree.fromstring(arch)

    def _visible_payment_buttons(self, form, move_type, has_outstanding):
        values = {
            "state": "posted",
            "payment_state": "not_paid",
            "move_type": move_type,
            "invoice_has_outstanding": has_outstanding,
            # added to the "Pay" buttons by account_payment (auto-installed)
            "authorized_transaction_ids": False,
        }
        return [
            button.get("string")
            for button in form.xpath("//button[@name='action_register_payment']")
            if not safe_eval(button.get("invisible", "False"), values)
        ]

    def test_form_buttons(self):
        form = self._arch("account.view_move_form", "form")
        collect = form.xpath("//button[@id='account_invoice_collect_btn']")
        collect_secondary = form.xpath("//button[@id='account_invoice_collect_secondary_btn']")
        self.assertEqual(len(collect), 1)
        self.assertEqual(len(collect_secondary), 1)
        for button in collect + collect_secondary:
            self.assertEqual(button.get("string"), "Collect")
            self.assertIn(
                "move_type not in ('out_invoice', 'out_refund', 'out_receipt')",
                button.get("invisible"),
            )
        self.assertEqual(collect[0].get("class"), "oe_highlight")
        for button_id in ("account_invoice_payment_btn", "account_invoice_payment_secondary_btn"):
            pay = form.xpath("//button[@id='%s']" % button_id)[0]
            self.assertEqual(pay.get("string"), "Pay")
            invisible = pay.get("invisible")
            # Original condition kept, customer types appended. Other modules
            # (account_payment) may append their own condition too, and the
            # resolved arch wraps each part in parentheses.
            self.assertIn(
                "move_type not in ('out_invoice', 'out_refund', 'in_invoice', "
                "'in_refund', 'out_receipt', 'in_receipt')",
                invisible,
            )
            self.assertIn(
                " or (move_type in ('out_invoice', 'out_refund', 'out_receipt'))", invisible
            )

    def test_form_one_button_per_move_type(self):
        form = self._arch("account.view_move_form", "form")
        for has_outstanding in (False, True):
            for move_type in CUSTOMER_TYPES:
                self.assertEqual(
                    self._visible_payment_buttons(form, move_type, has_outstanding), ["Collect"]
                )
            for move_type in VENDOR_TYPES:
                self.assertEqual(
                    self._visible_payment_buttons(form, move_type, has_outstanding), ["Pay"]
                )
            self.assertEqual(self._visible_payment_buttons(form, "entry", has_outstanding), [])

    def test_form_button_translated(self):
        form = self._arch("account.view_move_form", "form", lang="es_AR")
        button = form.xpath("//button[@id='account_invoice_collect_btn']")[0]
        self.assertEqual(button.get("string"), "Cobrar")

    def test_list_buttons(self):
        for view_xmlid, expected in (
            ("account.view_out_invoice_tree", "Collect"),
            ("account.view_out_credit_note_tree", "Collect"),
            ("account.view_in_invoice_tree", "Pay"),
            ("account.view_in_invoice_bill_tree", "Pay"),
            ("account.view_in_invoice_refund_tree", "Pay"),
            ("account.view_invoice_tree", "Pay"),
        ):
            arch = self._arch(view_xmlid, "list")
            button = arch.xpath("//header/button[@name='action_force_register_payment']")
            self.assertEqual(len(button), 1, view_xmlid)
            self.assertEqual(button[0].get("string"), expected, view_xmlid)

    def test_renamed_records(self):
        for xmlid, (name_en, name_es) in RENAMED.items():
            record = self.env.ref(xmlid)
            self.assertEqual(record.with_context(lang="en_US").name, name_en, xmlid)
            self.assertEqual(record.with_context(lang="es_AR").name, name_es, xmlid)

    def test_vendor_payment_records_untouched(self):
        for xmlid, name_en, name_es in (
            ("account.menu_action_account_payments_payable", "Payments", "Pagos"),
            ("account.action_account_payments_payable", "Vendor Payments", "Pagos de proveedor"),
        ):
            record = self.env.ref(xmlid)
            self.assertEqual(record.with_context(lang="en_US").name, name_en, xmlid)
            self.assertEqual(record.with_context(lang="es_AR").name, name_es, xmlid)

    def test_forced_translations_replace_existing_ones(self):
        """The module's po must win over a translation the record already
        has (what account leaves behind when this module is installed)."""
        menu = self.env.ref("account.menu_action_account_payments_receivable")
        menu.update_field_translations("name", {"es_AR": "Pagos"})
        self.assertEqual(menu.with_context(lang="es_AR").name, "Pagos")
        self.env["ir.module.module"]._account_translation_improvements_force_translations()
        self.assertEqual(menu.with_context(lang="es_AR").name, "Cobros")

    def test_uninstall_hook_restores_names(self):
        uninstall_hook(self.env)
        for xmlid, name_en, name_es in (
            ("account.action_move_force_register_payment", "Pay", "Pagar"),
            ("account.menu_action_account_payments_receivable", "Payments", "Pagos"),
            ("account.action_account_payments", "Customer Payments", "Pagos del cliente"),
            ("account.menu_action_move_in_refund_type", "Refunds", "Reembolsos"),
            ("account.action_move_in_refund_type", "Refunds", "Reembolsos"),
        ):
            record = self.env.ref(xmlid)
            self.assertEqual(record.with_context(lang="en_US").name, name_en, xmlid)
            self.assertEqual(record.with_context(lang="es_AR").name, name_es, xmlid)
