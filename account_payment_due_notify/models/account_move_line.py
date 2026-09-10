from markupsafe import Markup

from odoo import _, models
from odoo.tools import format_date, formatLang

_CELL_STYLE = "padding: 4px 16px 4px 0;"
_CELL_STYLE_RIGHT = "padding: 4px 0 4px 16px; text-align: right;"

# "Open external link" icon (Zinapsia standard, see CLAUDE.md) as an inline
# SVG data URI: email clients don't load Odoo's own icon font, so this is
# self-contained instead of relying on a webfont/external asset.
_EXTERNAL_LINK_ICON_SRC = Markup(
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 24 24' width='14' height='14' fill='none' "
    "stroke='%2300A0A9' stroke-width='2' stroke-linecap='round' "
    "stroke-linejoin='round'%3E%3Cpath d='M18 13v6a2 2 0 0 1-2 2H5a2 2 "
    "0 0 1-2-2V8a2 2 0 0 1 2-2h6'/%3E%3Cpolyline points='15 3 21 3 21 "
    "9'/%3E%3Cline x1='10' y1='14' x2='21' y2='3'/%3E%3C/svg%3E"
)


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
        """A small "open external link" icon linking to the document,
        used instead of a text link so the "Document" column stays
        compact.
        """
        self.ensure_one()
        move = self.move_id
        url = "%s/web#id=%s&model=account.move&view_type=form" % (
            move.get_base_url(),
            move.id,
        )
        icon = Markup(
            '<img src="%s" alt="%s" width="14" height="14" '
            'style="vertical-align: middle;"/>'
        ) % (_EXTERNAL_LINK_ICON_SRC, _("view document"))
        return Markup('<a href="%s" title="%s">%s</a>') % (url, _("view document"), icon)

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
