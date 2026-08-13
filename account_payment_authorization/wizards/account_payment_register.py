from odoo import models

VENDOR_BILL_TYPES = ("in_invoice", "in_refund")


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _init_payments(self, to_process, edit_mode=False):
        # Capture, for each payment being created, the single vendor bill it
        # is meant to pay -- before the payment gets posted (`_post_payments`)
        # and reconciled (`_reconcile_payments`), which both happen after
        # `_init_payments` in `_create_payments()`. At `action_post()` time,
        # `reconciled_invoice_ids` is not populated yet (reconciliation
        # hasn't run) and `invoice_ids` is never set by this wizard (it is
        # only written to by the online/portal payment flow), so this is the
        # only reliable point to identify the source bill for authorization
        # scheme matching. See authorization_invoice_id on account.payment
        # for details.
        payments = super()._init_payments(to_process, edit_mode=edit_mode)
        for payment, vals in zip(payments, to_process):
            lines = vals.get("to_reconcile")
            if not lines:
                continue
            bills = lines.move_id.filtered(
                lambda move: move.move_type in VENDOR_BILL_TYPES
            )
            if len(bills) == 1:
                payment.authorization_invoice_id = bills
        return payments
