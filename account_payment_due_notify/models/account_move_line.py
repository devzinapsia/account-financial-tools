from markupsafe import Markup

from odoo import _, fields, models
from odoo.tools import format_date, formatLang


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    payment_due_notice_1_sent = fields.Datetime(
        string="First payment due notice sent",
        copy=False,
        help="Date and time the first payment due notice was sent for "
        "this journal item. Empty means it has not been sent yet.",
    )
    payment_due_notice_2_sent = fields.Datetime(
        string="Second payment due notice sent",
        copy=False,
        help="Date and time the second payment due notice was sent for "
        "this journal item. Empty means it has not been sent yet.",
    )

    def _get_payment_due_notice_document_label(self):
        self.ensure_one()
        move = self.move_id
        # l10n_latam_document_type_id only exists when
        # l10n_latam_invoice_document is installed, which is not the case
        # in every deployment reusing this module.
        if (
            "l10n_latam_document_type_id" in move._fields
            and move.l10n_latam_document_type_id
        ):
            return "%s %s" % (
                move.l10n_latam_document_type_id.name,
                move.l10n_latam_document_number or move.name,
            )
        return _("Journal Entry %s", move.name)

    def _get_payment_due_notice_link(self):
        self.ensure_one()
        move = self.move_id
        url = "%s/web#id=%s&model=account.move&view_type=form" % (
            move.get_base_url(),
            move.id,
        )
        return Markup('<a href="%s">%s</a>') % (url, _("view document"))

    def _get_payment_due_notice_amount(self):
        self.ensure_one()
        currency = self.currency_id or self.company_currency_id
        amount = (
            self.amount_residual_currency
            if self.currency_id
            else self.amount_residual
        )
        return formatLang(self.env, amount, currency_obj=currency)

    def _get_payment_due_notice_row(self):
        """One <tr> of the notification digest table for this line."""
        self.ensure_one()
        return Markup(
            "<tr><td>%s</td><td>%s (%s)</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        ) % (
            self.partner_id.name,
            self._get_payment_due_notice_document_label(),
            self._get_payment_due_notice_link(),
            self.move_id.ref or "",
            format_date(self.env, self.date_maturity),
            self._get_payment_due_notice_amount(),
        )
