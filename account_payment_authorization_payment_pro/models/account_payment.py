from odoo import Command, api, models

VENDOR_BILL_TYPES = ("in_invoice", "in_refund")


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _sync_invoice_ids_from_payment_pro(self):
        """account_payment_pro replaces the core "Register Payment" wizard
        (`account.payment.register`) entirely: the user drafts the
        `account.payment` record directly, and the bill it's meant to
        settle is tracked on the payment itself via `to_pay_move_line_ids`,
        populated well before `action_post()` runs -- reconciliation with
        those lines only happens *after* `action_post()` succeeds (see
        that module's `_reconcile_after_post()`), so by the time our
        authorization gate runs, the debt is already known even though it
        isn't reconciled yet.

        Mirror the vendor bill into the core `invoice_ids` field -- the one
        account_payment_authorization scheme conditions are meant to
        reference -- so conditions work the same regardless of which flow
        created the payment.
        """
        for payment in self:
            if payment.payment_type != "outbound" or payment.partner_type != "supplier":
                continue
            bills = payment.to_pay_move_line_ids.move_id.filtered(
                lambda move: move.move_type in VENDOR_BILL_TYPES
            )
            if len(bills) == 1 and bills not in payment.invoice_ids:
                payment.invoice_ids = [Command.link(bills.id)]

    @api.depends("to_pay_move_line_ids", "to_pay_move_line_ids.move_id.classification_id")
    def _compute_matched_scheme_ids(self):
        self._sync_invoice_ids_from_payment_pro()
        super()._compute_matched_scheme_ids()

    def _refresh_authorization_state(self):
        self._sync_invoice_ids_from_payment_pro()
        return super()._refresh_authorization_state()
