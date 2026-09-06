import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools.arca_xlsx_parser import ArcaFileFormatError, normalize_vat, parse_arca_file


class ArcaBillComparisonWizard(models.TransientModel):
    _name = "arca.bill.comparison.wizard"
    _description = "ARCA My Vouchers Received - Import Wizard"

    file = fields.Binary(string="File to import", required=True)
    filename = fields.Char(string="Filename")
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")

    @api.onchange("file")
    def _onchange_file(self):
        if not self.file:
            return
        try:
            rows = parse_arca_file(base64.b64decode(self.file))
        except ArcaFileFormatError as exc:
            return {"warning": {"title": _("Invalid file"), "message": str(exc)}}
        dates = [row["date"] for row in rows if row["date"]]
        if dates:
            self.date_from = min(dates)
            self.date_to = max(dates)

    def action_process(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("Please attach a file to import."))
        try:
            rows = parse_arca_file(base64.b64decode(self.file))
        except ArcaFileFormatError as exc:
            raise UserError(str(exc)) from exc
        if not rows:
            raise UserError(_("The selected file has no voucher rows to compare."))

        company = self.env.company
        file_recipient_vat = normalize_vat(rows[0]["recipient_vat"])
        company_vat = normalize_vat(company.vat)
        if file_recipient_vat != company_vat:
            # Exact wording mandated by the ARCA control process spec (kept
            # in Spanish verbatim, including the unbalanced parenthesis, on
            # explicit client request instead of the usual English-source
            # + es/es_AR translation convention).
            raise UserError(
                _(
                    "El archivo a importar no pertenece a la empresa actual "
                    "(CUIT del receptor %(file_vat)s diferente al de la empresa %(company_vat)s"
                )
                % {"file_vat": rows[0]["recipient_vat"], "company_vat": company.vat}
            )

        dates = [row["date"] for row in rows if row["date"]]
        date_from = self.date_from or min(dates)
        date_to = self.date_to or max(dates)

        batch = self.env["arca.bill.comparison.batch"].create(
            {
                "company_id": company.id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        batch._run_comparison(rows)
        return batch.action_view_lines()
