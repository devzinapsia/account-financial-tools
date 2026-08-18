from odoo import Command, api, models

VENDOR_BILL_TYPES = ("in_invoice", "in_refund")


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_authorization_sensitive_fields(self):
        # Under account_payment_pro, to_pay_move_line_ids -- not
        # invoice_ids -- is what the user actually edits to change which
        # bill a payment settles. invoice_ids does get updated too, but
        # only lazily, as a side effect the next time something reads
        # matched_scheme_ids/pending_authorizer_ids (see
        # _sync_invoice_ids_from_payment_pro below); listing this field
        # here makes the base module's write() override reset the
        # authorization immediately on the same write, instead of only
        # once that lazy sync happens to run.
        return super()._get_authorization_sensitive_fields() | {"to_pay_move_line_ids"}

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

        Uses `Command.set` (replace), not `Command.link` (add): the user
        can change `to_pay_move_line_ids` after picking it once (swap the
        bill, add a second one, clear it), and `invoice_ids` must track
        that current selection exactly, not accumulate every bill ever
        selected. A stale extra entry here wouldn't just make our own
        scheme matching wrong -- `invoice_ids` is also read directly by
        `l10n_ar_payment_bundle.button_open_invoices()` and by core's own
        `reconciled_bill_ids` stat button count
        (`_compute_stat_buttons_from_reconciliation` starts from
        `payment.invoice_ids` before adding the actual reconciliation
        query), so leaving old links behind would leak into those too.
        """
        for payment in self:
            if payment.payment_type != "outbound" or payment.partner_type != "supplier":
                continue
            bills = payment.to_pay_move_line_ids.move_id.filtered(
                lambda move: move.move_type in VENDOR_BILL_TYPES
            )
            # Scope stays "a single identifiable bill": if to_pay_move_line_ids
            # currently spans zero or several bills, invoice_ids is cleared
            # rather than guessing -- matching account_payment_authorization's
            # documented "one bill per payment" scope.
            target_ids = bills.ids if len(bills) == 1 else []
            if set(target_ids) != set(payment.invoice_ids.ids):
                payment.invoice_ids = [Command.set(target_ids)]

    @api.depends("to_pay_move_line_ids", "to_pay_move_line_ids.move_id.classification_id")
    def _compute_matched_scheme_ids(self):
        self._sync_invoice_ids_from_payment_pro()
        super()._compute_matched_scheme_ids()

    def _refresh_authorization_state(self):
        self._sync_invoice_ids_from_payment_pro()
        return super()._refresh_authorization_state()
