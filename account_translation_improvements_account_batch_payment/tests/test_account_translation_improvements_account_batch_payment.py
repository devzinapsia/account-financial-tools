from odoo.tests import TransactionCase, tagged

from ..hooks import uninstall_hook

MODULE = "account_translation_improvements_account_batch_payment"
MENU = "account_batch_payment.menu_batch_payment_sales"
ACTION = "account_batch_payment.action_batch_payment_in"


@tagged("post_install", "-at_install")
class TestAccountTranslationImprovementsBatchPayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.env["res.lang"]._get_data(code="es_AR"):
            # Activating a language loads every module's terms in dependency
            # order, so this module's names win over account_batch_payment's.
            cls.env["res.lang"]._activate_lang("es_AR")
            cls.env["ir.module.module"].search(
                [("name", "in", ("account_batch_payment", MODULE))]
            )._update_translations("es_AR")

    def _names(self, xmlid):
        record = self.env.ref(xmlid)
        return record.with_context(lang="en_US").name, record.with_context(lang="es_AR").name

    def test_customer_records_renamed(self):
        for xmlid in (MENU, ACTION):
            self.assertEqual(self._names(xmlid), ("Batch Collections", "Cobros por lotes"), xmlid)

    def test_vendor_records_untouched(self):
        self.assertEqual(
            self._names("account_batch_payment.menu_batch_payment_purchases"),
            ("Batch Payments", "Pagos por lotes"),
        )
        self.assertEqual(
            self.env.ref("account_batch_payment.action_batch_payment_out")
            .with_context(lang="en_US").name,
            "Vendor Batch Payments",
        )

    def test_forced_translations_replace_existing_ones(self):
        menu = self.env.ref(MENU)
        menu.update_field_translations("name", {"es_AR": "Pagos por lotes"})
        self.env["ir.module.module"]._account_translation_improvements_account_batch_payment_force_translations()
        self.assertEqual(menu.with_context(lang="es_AR").name, "Cobros por lotes")

    def test_uninstall_hook_restores_names(self):
        uninstall_hook(self.env)
        self.assertEqual(self._names(MENU), ("Batch Payments", "Pagos por lotes"))
        self.assertEqual(
            self._names(ACTION), ("Customer Batch Payments", "Pagos por lote del cliente")
        )
