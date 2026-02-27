from odoo import models, api, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_draft(self):
        """ Sobreescribimos la acción de pasar a borrador """
        self._check_afip_auth_code()
        return super(AccountMove, self).action_draft()

    def button_draft(self):
        """ Sobreescribimos el botón de la interfaz que llama al borrador """
        self._check_afip_auth_code()
        return super(AccountMove, self).button_draft()

    def _check_afip_auth_code(self):
        """ Método privado para validar la presencia de CAE """
        for rec in self:
            # Verificamos solo en facturas y notas de crédito de clientes
            if rec.move_type in ['out_invoice', 'out_refund']:
                # Usamos el nombre técnico exacto de tu captura: l10n_ar_afip_auth_code
                if rec.l10n_ar_afip_auth_code:
                    raise ValidationError(_(
                        "Seguridad Zinapsia: No se puede pasar a borrador la factura %s "
                        "porque ya posee CAE de AFIP (%s). Debe anularse mediante Nota de Crédito."
                    ) % (rec.name, rec.l10n_ar_afip_auth_code))