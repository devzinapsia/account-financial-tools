from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    # The journal entry of a payment can be reset, cancelled or reversed on
    # its own, from the entry form: lock it like its payment.

    def button_draft(self):
        self.origin_payment_id._check_intercompany_transfer_unlocked()
        return super().button_draft()

    def button_cancel(self):
        self.origin_payment_id._check_intercompany_transfer_unlocked()
        return super().button_cancel()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        self.origin_payment_id._check_intercompany_transfer_unlocked()
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    def unlink(self):
        self.origin_payment_id._check_intercompany_transfer_unlocked()
        return super().unlink()
