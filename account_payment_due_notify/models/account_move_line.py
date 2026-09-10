from markupsafe import Markup

from odoo import _, models
from odoo.tools import format_date, formatLang

_CELL_STYLE = "padding: 4px 16px 4px 0;"
_CELL_STYLE_RIGHT = "padding: 4px 0 4px 16px; text-align: right;"


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

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
        """A small calendar-icon link to the document, used instead of a
        text link so the "Document" column stays compact.
        """
        self.ensure_one()
        move = self.move_id
        url = "%s/web#id=%s&model=account.move&view_type=form" % (
            move.get_base_url(),
            move.id,
        )
        return Markup('<a href="%s" title="%s">\U0001F4C5</a>') % (url, _("view document"))

    def _get_payment_due_notice_amount(self):
        self.ensure_one()
        currency = self.currency_id or self.company_currency_id
        amount = (
            self.amount_residual_currency
            if self.currency_id
            else self.amount_residual
        )
        return formatLang(self.env, amount, currency_obj=currency)

    def _get_payment_due_notice_row(self, include_due_date=False):
        """One <tr> of the notification digest table for this line."""
        self.ensure_one()
        cells = []
        if include_due_date:
            cells.append(
                Markup('<td style="%s">%s</td>')
                % (_CELL_STYLE, format_date(self.env, self.date_maturity))
            )
        cells.append(Markup('<td style="%s">%s</td>') % (_CELL_STYLE, self.partner_id.name))
        cells.append(
            Markup('<td style="%s">%s %s</td>')
            % (
                _CELL_STYLE,
                self._get_payment_due_notice_document_label(),
                self._get_payment_due_notice_link(),
            )
        )
        cells.append(
            Markup('<td style="%s">%s</td>') % (_CELL_STYLE, self.move_id.ref or "")
        )
        cells.append(
            Markup('<td style="%s">%s</td>')
            % (_CELL_STYLE_RIGHT, self._get_payment_due_notice_amount())
        )
        return Markup("<tr>%s</tr>") % Markup("").join(cells)
