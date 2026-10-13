from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .account_intercompany_transfer import is_internal_write

# Fields core and ingadhoc's account_internal_transfer use to recognize their
# own internal transfers. A payment of an intercompany transfer must carry
# none of them, so it never enters those processes, and a payment carrying
# any of them can't be linked to an intercompany transfer. The ingadhoc ones
# only exist when that module is installed.
FOREIGN_TRANSFER_MARKERS = (
    "paired_internal_transfer_payment_id",
    "is_internal_transfer",
    "destination_journal_id",
)

# What defines the money movement of a payment of an intercompany transfer:
# locked while the transfer is posted, it is changed by cancelling the
# transfer and creating a new one.
LOCKED_PAYMENT_FIELDS = {
    "amount",
    "currency_id",
    "date",
    "destination_account_id",
    "intercompany_transfer_id",
    "journal_id",
    "memo",
    "partner_id",
    "partner_type",
    "payment_method_line_id",
    "payment_type",
}


class AccountPayment(models.Model):
    _inherit = "account.payment"

    intercompany_transfer_id = fields.Many2one(
        "account.intercompany.transfer",
        string="Intercompany transfer",
        index="btree_not_null",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    @api.depends("intercompany_transfer_id")
    def _compute_destination_account_id(self):
        # The counterpart is always the bridge account of the payment's own
        # company, whatever other modules compute for regular payments.
        super()._compute_destination_account_id()
        for payment in self.filtered("intercompany_transfer_id"):
            payment.destination_account_id = payment.company_id.intercompany_transfer_account_id

    @api.constrains("intercompany_transfer_id", "paired_internal_transfer_payment_id")
    def _check_intercompany_transfer_id(self):
        for payment in self.filtered("intercompany_transfer_id"):
            transfer = payment.intercompany_transfer_id
            markers = payment._get_foreign_transfer_markers()
            if markers:
                raise ValidationError(
                    _(
                        "The payment %(payment)s is an internal transfer (%(markers)s) and can't be "
                        "part of the intercompany transfer %(transfer)s.",
                        payment=payment.display_name,
                        markers=", ".join(markers),
                        transfer=transfer.display_name,
                    )
                )
            if payment not in transfer.origin_payment_id | transfer.destination_payment_id and not (
                is_internal_write()
            ):
                raise ValidationError(
                    _(
                        "The payment %(payment)s was not created by the intercompany transfer %(transfer)s.",
                        payment=payment.display_name,
                        transfer=transfer.display_name,
                    )
                )

    def _get_foreign_transfer_markers(self):
        """Labels of the core/ingadhoc internal transfer fields set on the payment."""
        self.ensure_one()
        return [
            self._fields[name].string
            for name in FOREIGN_TRANSFER_MARKERS
            if name in self._fields and self[name]
        ]

    # ------------------------------------------------------------------
    # Protection of the payments of a posted transfer
    # ------------------------------------------------------------------

    def _check_intercompany_transfer_unlocked(self):
        if is_internal_write():
            return
        locked = self.filtered(lambda p: p.intercompany_transfer_id.state == "posted")
        if locked:
            raise UserError(
                _(
                    "The payment %(payment)s belongs to the intercompany transfer %(transfer)s. "
                    "Cancel the transfer instead of changing its payments.",
                    payment=locked[0].display_name,
                    transfer=locked[0].intercompany_transfer_id.display_name,
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal_write() and any(vals.get("intercompany_transfer_id") for vals in vals_list):
            raise UserError(_("Payments of intercompany transfers can only be created by the transfer wizard."))
        return super().create(vals_list)

    def write(self, vals):
        if any(vals.get(name) for name in FOREIGN_TRANSFER_MARKERS) and self.filtered("intercompany_transfer_id"):
            raise UserError(_("A payment of an intercompany transfer can't be turned into an internal transfer."))
        if LOCKED_PAYMENT_FIELDS & set(vals):
            if "intercompany_transfer_id" in vals and not is_internal_write():
                raise UserError(_("A payment can't be linked to an intercompany transfer by hand."))
            self._check_intercompany_transfer_unlocked()
        if vals.get("state") in ("draft", "canceled", "rejected"):
            self._check_intercompany_transfer_unlocked()
        return super().write(vals)

    def unlink(self):
        if not is_internal_write() and self.filtered("intercompany_transfer_id"):
            raise UserError(_("Payments of intercompany transfers can't be deleted."))
        return super().unlink()

    def action_draft(self):
        self._check_intercompany_transfer_unlocked()
        return super().action_draft()

    def action_cancel(self):
        self._check_intercompany_transfer_unlocked()
        return super().action_cancel()

    def action_reject(self):
        self._check_intercompany_transfer_unlocked()
        return super().action_reject()
