from .common import DefaultAccountCommon

class TestDefaultAccount(DefaultAccountCommon):
    
    def test_default_account_and_taxes_no_product(self):
        """ Verificar que carga Cuenta e Impuestos del Partner sin producto """
        # Arrange
        self.partner.property_account_income = self.partner_account
        self.partner.default_income_tax_ids = [(6, 0, [self.test_tax.id])]

        # Act
        invoice = self._create_invoice(self.env.user, self.partner)
        line = invoice.invoice_line_ids[0]

        # Assert
        self.assertEqual(line.account_id, self.partner_account)
        self.assertIn(self.test_tax, line.tax_ids)

    def test_default_account_no_autosave(self):
        """ Verificar que NO actualiza el partner si el check está apagado """
        self.partner.auto_update_account_income = False
        self.partner.property_account_income = self.partner_account
        
        # Act: Creamos factura con otra cuenta
        invoice = self._create_invoice(self.env.user, self.partner)
        invoice.invoice_line_ids[0].account_id = self.other_account
        invoice.action_post() # El autoguardar suele dispararse al validar o confirmar

        # Assert: La cuenta del partner sigue siendo la original
        self.assertEqual(self.partner.property_account_income, self.partner_account)