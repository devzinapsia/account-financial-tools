from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

L10N_AR_MANUAL_POS_SYSTEM = "II_IM"
L10N_AR_SERVICE_CONCEPTS = ("2", "3")


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ar_service_period_dates_required = fields.Boolean(
        compute="_compute_l10n_ar_service_period_dates_required",
        store=True,
        string="ARCA service period dates required",
    )

    @api.depends(
        "move_type",
        "journal_id",
        "journal_id.type",
        "journal_id.l10n_ar_afip_pos_system",
        "journal_id.l10n_ar_service_period_dates_required",
        "invoice_line_ids",
    )
    def _compute_l10n_ar_service_period_dates_required(self):
        for move in self:
            move.l10n_ar_service_period_dates_required = (
                move._l10n_ar_compute_service_period_dates_required()
            )

    def _l10n_ar_compute_service_period_dates_required(self):
        """Whether the ARCA service billing period (start/end dates) is
        mandatory for this invoice.

        This is the single source of truth for the condition, reused by the
        stored compute field above and by the posting check below. Drafts
        are never blocked by this: the dates are only required to confirm
        (post) the invoice, mirroring how account.move._post() itself
        collects "required only when posting" checks (e.g. partner, invoice
        date) instead of enforcing them on every draft save.
        """
        self.ensure_one()
        journal = self.journal_id
        return bool(
            self.move_type in ("out_invoice", "out_refund")
            and journal.type == "sale"
            and journal.l10n_ar_afip_pos_system
            and journal.l10n_ar_afip_pos_system != L10N_AR_MANUAL_POS_SYSTEM
            and journal.l10n_ar_service_period_dates_required
            and self.l10n_ar_afip_concept in L10N_AR_SERVICE_CONCEPTS
        )

    def _post(self, soft=True):
        for move in self:
            if move._l10n_ar_compute_service_period_dates_required() and not (
                move.l10n_ar_afip_service_start and move.l10n_ar_afip_service_end
            ):
                raise ValidationError(
                    _(
                        "You must fill in the service billing period "
                        "required by ARCA, in the Other Info tab."
                    )
                )
        return super()._post(soft=soft)
