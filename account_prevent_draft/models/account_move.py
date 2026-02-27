from odoo import models, api, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_draft(self):
        for rec in self:
            # Filtramos por facturas y notas de crédito de cliente
            if rec.move_type in ['out_invoice', 'out_refund']:
                # Verificamos si tiene CAE (afip_auth_code)
                if rec.afip_auth_code:
                    raise ValidationError(_(
                        "No se puede pasar a borrador la factura %s porque ya posee CAE (%s). "
                        "Debe realizar una nota de crédito si desea anularla."
                    ) % (rec.name, rec.afip_auth_code))
        
        return super().action_draft()