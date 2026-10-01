from odoo import fields, models


class AccountVendorBillAuthorizationRejectWizard(models.TransientModel):
    _name = "account.vendor.bill.authorization.reject.wizard"
    _description = "Reject Vendor Bill Authorization"

    move_id = fields.Many2one(
        "account.move",
        string="Vendor bill",
        required=True,
        readonly=True,
    )
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        # Permission and state are re-checked server-side by _reject_bill(),
        # not only when the wizard was opened.
        self.move_id._reject_bill(self.reason)
        return {"type": "ir.actions.act_window_close"}
