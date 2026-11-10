import logging
import re
from collections import defaultdict

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Characters not allowed in file names on common systems (Windows is the most
# restrictive), plus control characters.
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')

PDF_MIMETYPE = "application/pdf"


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_payment_email_attachment_name(self):
        """File name of this document's PDF when attached to a payment email:
        its name (number) with the characters invalid in file names replaced."""
        self.ensure_one()
        name = INVALID_FILENAME_CHARS.sub("_", self.name or "").strip(" .") or str(self.id)
        return f"{name}.pdf"

    def _get_payment_email_vendor_pdf(self):
        """The PDF attached to this vendor bill / credit note: its main
        attachment when it is a PDF, otherwise its first PDF attachment."""
        self.ensure_one()
        main_attachment = self.message_main_attachment_id
        if main_attachment and main_attachment.mimetype == PDF_MIMETYPE:
            return main_attachment
        return self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("mimetype", "=", PDF_MIMETYPE),
            ],
            order="id",
            limit=1,
        )

    def _get_payment_email_pdfs(self):
        """Return {move: PDF content (bytes)} for the documents of self that
        have one:

        * sales documents: the same PDF the customer receives when the document
          is sent. The stored one when it exists, otherwise it is rendered with
          the report the sending flow would use, without storing it;
        * purchase documents: the PDF attached to the document. Without one,
          the document is left out.
        """
        result = {}
        to_render = defaultdict(lambda: self.env["account.move"])
        move_send = self.env["account.move.send"]
        for move in self:
            if move.is_sale_document():
                if move.invoice_pdf_report_id:
                    result[move] = move.invoice_pdf_report_id.raw
                    continue
                try:
                    report = move_send._get_default_pdf_report_id(move)
                except UserError as error:
                    _logger.warning("No PDF report for %s, not attached to the payment email: %s", move.name, error)
                    continue
                to_render[(report, move.company_id)] |= move
            elif move.is_purchase_document():
                attachment = move._get_payment_email_vendor_pdf()
                if attachment:
                    result[move] = attachment.raw

        # Same rendering as account.move.send._prepare_invoice_pdf_report, but
        # without account.move.send._link_invoice_documents: nothing is stored
        # on the documents.
        reports = self.env["ir.actions.report"]
        for (report, company), moves in to_render.items():
            content, report_type = reports.with_company(company)._pre_render_qweb_pdf(
                report.report_name, res_ids=moves.ids
            )
            content_by_id = reports._get_splitted_report(report.report_name, content, report_type)
            for move in moves:
                if content_by_id.get(move.id):
                    result[move] = content_by_id[move.id]
        return result
