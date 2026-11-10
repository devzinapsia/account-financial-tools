from odoo import models

# Documents that can be attached to a payment email: invoices and credit
# notes, of sales or purchases (receipts and journal entries are not).
EMAIL_INVOICE_MOVE_TYPES = ("out_invoice", "out_refund", "in_invoice", "in_refund")


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _email_invoices_enabled(self):
        """Whether the company of this payment attaches invoices to its emails:
        payment orders (outbound) and receipts (inbound) have their own setting."""
        self.ensure_one()
        if self.payment_type == "outbound":
            return self.company_id.attach_invoices_on_payment_order
        if self.payment_type == "inbound":
            return self.company_id.attach_invoices_on_receipt
        return False

    def _get_email_invoice_payments(self):
        """Payments whose journal entries settle the documents of this
        payment's email. Hook for modules where one payment is made of several
        (e.g. a payment bundle and its linked payments)."""
        self.ensure_one()
        return self

    def _get_email_invoice_candidates(self):
        """Return the documents that intervene in this payment:

        * the documents reconciled with its receivable / payable journal items;
        * the documents reconciled with those in the same operation, i.e. the
          credit notes applied within the payment: the payment wizards
          reconcile the payment, the invoices and the credit notes in one call,
          and a credit note ends up reconciled with an invoice, not with the
          payment. Partials of one operation share their create_date (the
          transaction timestamp); a credit note applied before is left out.

        invoice_ids is not used for payments with a journal entry: the core
        payment wizard links all the selected documents to all their previous
        payments too (e.g. a partial payment of one invoice gets linked to the
        other invoices paid later together with it)."""
        self.ensure_one()
        payments = self._get_email_invoice_payments()
        payment_lines = payments.move_id.line_ids.filtered(
            lambda line: line.account_type in ("asset_receivable", "liability_payable")
        )
        if not payment_lines:
            # A payment without journal entry is only linked through invoice_ids.
            return payments.invoice_ids
        own_partials = payment_lines.matched_debit_ids | payment_lines.matched_credit_ids
        settled_lines = (own_partials.debit_move_id | own_partials.credit_move_id) - payment_lines
        settled_lines = settled_lines._filtered_access("read")
        operation_dates = set(own_partials.mapped("create_date"))
        same_operation = (settled_lines.matched_debit_ids | settled_lines.matched_credit_ids).filtered(
            lambda partial: partial.create_date in operation_dates
        )
        related_lines = (same_operation.debit_move_id | same_operation.credit_move_id) - payment_lines
        related_lines = related_lines._filtered_access("read")
        return (settled_lines | related_lines).move_id - payments.move_id

    def _get_email_invoices(self):
        """Return the documents whose PDF is attached when this payment is sent
        by email: posted invoices and credit notes that the current user can
        read, outside the journals excluded by the payment's company."""
        self.ensure_one()
        if not self._email_invoices_enabled():
            return self.env["account.move"]
        # Read access is checked for the current user: a document the user
        # can't read is never attached.
        candidates = self._get_email_invoice_candidates()._filtered_access("read")
        excluded_journals = self.company_id.no_attachment_journal_ids
        return candidates.filtered(
            lambda move: move.move_type in EMAIL_INVOICE_MOVE_TYPES
            and move.state == "posted"
            and move.journal_id not in excluded_journals
        ).sorted(lambda move: (move.invoice_date or move.date, move.name or "", move.id))
