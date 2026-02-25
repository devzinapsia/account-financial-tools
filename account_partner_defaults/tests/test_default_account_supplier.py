def test_default_account_autosave_supplier(self):
        # ... (todo el setup igual que antes)
        
        # Act: Cambiamos la cuenta en el Form
        invoice_form = Form(self.invoice)
        with invoice_form.invoice_line_ids.edit(0) as line:
            line.account_id = self.other_account
        invoice_form.save()
        
        # PUBLICAR la factura para disparar el _post y el autoguardado
        self.invoice.action_post()

        # Assert: Ahora sí debe haber cambiado
        self.assertEqual(self.partner.property_account_expense.id, self.other_account.id)