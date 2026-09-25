from odoo import _, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def button_draft(self):
        self._check_afip_auth_code()
        return super().button_draft()

    def _check_afip_auth_code(self):
        """Block resetting to draft customer invoices/credit notes that were
        authorized by ARCA through a web service journal (WSFE, WSFEX, WSBFE,
        or any other web service added by third-party modules).

        Journals without a web service (online invoice, pre-printed, etc.)
        are not blocked, even when a CAE was loaded manually on the invoice.
        """
        for rec in self:
            if (
                rec.move_type in ('out_invoice', 'out_refund')
                and rec.journal_id.l10n_ar_afip_ws
                and rec.l10n_ar_afip_auth_code
            ):
                raise ValidationError(_(
                    "Invoice %(name)s cannot be reset to draft because it was "
                    "authorized by ARCA through a web service (CAE %(cae)s). "
                    "It must be cancelled with a credit note.",
                    name=rec.name,
                    cae=rec.l10n_ar_afip_auth_code,
                ))
