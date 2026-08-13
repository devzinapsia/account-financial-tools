from odoo import Command, models

VENDOR_BILL_TYPES = ("in_invoice", "in_refund")


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _init_payments(self, to_process, edit_mode=False):
        # Capture, for each payment being created, the single vendor bill it
        # is meant to pay -- before the payment gets posted (`_post_payments`)
        # and reconciled (`_reconcile_payments`), which both happen after
        # `_init_payments` in `_create_payments()`. At `action_post()` time,
        # `reconciled_invoice_ids` is not populated yet (reconciliation
        # hasn't run), so this is the only reliable point to identify the
        # source bill for authorization scheme matching.
        #
        # `invoice_ids` is the core account.payment field meant for exactly
        # this ("contains the invoice even if they don't have a journal
        # entry and are not reconciled"), but core only ever writes to it
        # from the online/portal payment flow (`account_payment` module),
        # never from this internal Register Payment wizard -- so it is
        # normally empty for payments created this way. We fill it in here
        # so that authorization scheme conditions can reference it directly
        # (e.g. `invoice_ids.classification_id`), which is also what shows
        # up first/most intuitively in the scheme's domain field picker.
        payments = super()._init_payments(to_process, edit_mode=edit_mode)
        for payment, vals in zip(payments, to_process):
            lines = vals.get("to_reconcile")
            if not lines:
                continue
            bills = lines.move_id.filtered(
                lambda move: move.move_type in VENDOR_BILL_TYPES
            )
            if len(bills) == 1:
                payment.invoice_ids = [Command.link(bills.id)]
        return payments
