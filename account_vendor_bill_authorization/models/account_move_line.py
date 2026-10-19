from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _reconcile_plan(self, reconciliation_plan):
        # Safety net for every way of paying a vendor bill that ends in a
        # reconciliation (register payment, payment receipts, bank
        # reconciliation, applying an outstanding credit or a credit note
        # from the bill...): the payable line of a bill awaiting
        # authorization, or rejected, can't be reconciled. A full reversal
        # (move_reverse_cancel) is the exception: it cancels the bill.
        if not self.env.context.get("move_reverse_cancel"):
            lines = self._collect_reconciliation_plan_lines(reconciliation_plan)
            lines.filtered(
                lambda line: line.account_type in ("liability_payable", "asset_receivable")
            ).move_id._check_vendor_bill_authorization_before_payment()
        return super()._reconcile_plan(reconciliation_plan)

    def _collect_reconciliation_plan_lines(self, reconciliation_plan):
        """All the lines of a (possibly nested) reconciliation plan."""
        lines = self.browse()
        for item in reconciliation_plan:
            if isinstance(item, models.BaseModel):
                lines |= item
            else:
                lines |= self._collect_reconciliation_plan_lines(item)
        return lines
