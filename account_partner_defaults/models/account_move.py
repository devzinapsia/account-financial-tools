from odoo import api, models

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.onchange('partner_id')
    def _onchange_partner_id_set_journal(self):
        """ Asigna el diario por defecto del partner si es una factura de proveedor """
        for move in self:
            if move.is_purchase_document() and move.partner_id.property_purchase_journal_id:
                move.journal_id = move.partner_id.property_purchase_journal_id