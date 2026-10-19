from dateutil.relativedelta import relativedelta

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

    def _l10n_ar_is_electronic_service_invoice(self):
        """Whether this is a customer invoice/credit note of an electronic
        ARCA sales journal with an ARCA concept of Services or Products and
        Services.

        This is the business rule every journal option of this module is
        scoped to (dates required, default period and printing).
        """
        self.ensure_one()
        journal = self.journal_id
        return bool(
            self.move_type in ("out_invoice", "out_refund")
            and journal.type == "sale"
            and journal.l10n_ar_afip_pos_system
            and journal.l10n_ar_afip_pos_system != L10N_AR_MANUAL_POS_SYSTEM
            and self.l10n_ar_afip_concept in L10N_AR_SERVICE_CONCEPTS
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
        return bool(
            self.journal_id.l10n_ar_service_period_dates_required
            and self._l10n_ar_is_electronic_service_invoice()
        )

    def _l10n_ar_get_default_service_period(self):
        """Return the (start, end) service period proposed by the journal's
        default period option, or (False, False) when nothing applies."""
        self.ensure_one()
        mode = self.journal_id.l10n_ar_service_period_default
        if not (
            self.invoice_date
            and mode in ("invoice_month", "invoice_day")
            and self._l10n_ar_is_electronic_service_invoice()
        ):
            return False, False
        if mode == "invoice_day":
            return self.invoice_date, self.invoice_date
        return (
            self.invoice_date + relativedelta(day=1),
            self.invoice_date + relativedelta(day=1, days=-1, months=+1),
        )

    def _l10n_ar_print_service_period(self):
        """Whether the invoiced period is printed on the invoice report.
        Only electronic service invoices honor the journal option; any
        other document keeps the standard l10n_ar behavior."""
        self.ensure_one()
        return (
            self.journal_id.l10n_ar_service_period_print
            or not self._l10n_ar_is_electronic_service_invoice()
        )

    @api.onchange("invoice_date", "journal_id", "invoice_line_ids")
    def _onchange_l10n_ar_default_service_period(self):
        for move in self.filtered(
            lambda m: m.state == "draft"
            and not m.l10n_ar_afip_service_start
            and not m.l10n_ar_afip_service_end
        ):
            start, end = move._l10n_ar_get_default_service_period()
            if start:
                move.l10n_ar_afip_service_start = start
                move.l10n_ar_afip_service_end = end

    def _set_afip_service_dates(self):
        # Called by l10n_ar's _post() right after posting (and before
        # l10n_ar_edi requests the CAE): honor the "invoice day" default on
        # empty dates, the standard invoice month fallback covers the rest.
        for move in self.filtered(
            lambda m: m.journal_id.l10n_ar_service_period_default == "invoice_day"
        ):
            start, end = move._l10n_ar_get_default_service_period()
            if start:
                if not move.l10n_ar_afip_service_start:
                    move.l10n_ar_afip_service_start = start
                if not move.l10n_ar_afip_service_end:
                    move.l10n_ar_afip_service_end = end
        return super()._set_afip_service_dates()

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
