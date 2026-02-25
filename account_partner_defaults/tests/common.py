#  Copyright 2026 Zinapsia
#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.tests import Form, tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

@tagged("post_install", "-at_install")
class DefaultAccountCommon(AccountTestInvoicingCommon):

    _default_move_type = "out_invoice"

    @classmethod
    def _create_invoice(cls, user, partner, product=None):
        """
        Helper para crear facturas disparando onchanges.
        Incluye fecha y referencia para cumplir con validaciones de Odoo 18 y L10n_AR.
        """
        move_model = cls.env["account.move"].with_context(default_move_type=cls._default_move_type)
        if user:
            move_model = move_model.with_user(user)

        invoice_form = Form(move_model)
        invoice_form.partner_id = partner
        
        # Seteamos la fecha de factura (Requerido para in_invoice en Odoo 18)
        invoice_form.invoice_date = fields.Date.today()
        
        # Para facturas de proveedor, seteamos un número de comprobante (Requerido por l10n_ar)
        if cls._default_move_type == 'in_invoice':
            invoice_form.ref = '0001-00000001'

        with invoice_form.invoice_line_ids.new() as line:
            if product:
                line.product_id = product
        
        return invoice_form.save()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Deshabilitamos tracking y preparamos entorno limpio
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        # 1. Creamos un Partner de prueba Zinapsia
        cls.partner = cls.env['res.partner'].create({
            'name': 'Zinapsia Test Partner',
            'auto_update_account_income': True,
            'auto_update_account_expense': True,
        })
        
        # 2. Referencia a un producto del sistema
        cls.product = cls.env['product.product'].search([], limit=1)
        
        # 3. Buscamos cuenta contable compatible
        acc_type = 'income' if cls._default_move_type == 'out_invoice' else 'expense'
        cls.partner_account = cls.env['account.account'].search([
            ('account_type', '=', acc_type)
        ], limit=1)

        # 4. Creamos una cuenta extra para testear autoguardado (Código alfanumérico limpio)
        cls.other_account = cls.env["account.account"].create({
            "name": "Zinapsia Test Acc",
            "code": "Z999",
            "account_type": acc_type,
        })

        # 5. Buscamos o creamos un Impuesto de prueba
        tax_use = 'sale' if cls._default_move_type == 'out_invoice' else 'purchase'
        cls.test_tax = cls.env['account.tax'].search([
            ('type_tax_use', '=', tax_use)
        ], limit=1) or cls.env['account.tax'].create({
            'name': 'Tax Test Zinapsia',
            'amount': 21.0,
            'type_tax_use': tax_use,
        })

        # 6. Inicializamos factura base para los tests
        cls.invoice = cls._create_invoice(cls.env.user, cls.partner)