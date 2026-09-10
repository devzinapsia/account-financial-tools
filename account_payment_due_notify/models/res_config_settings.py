from odoo import api, fields, models
from odoo.addons.base.models.res_partner import _tz_get


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    payment_due_notify_enabled = fields.Boolean(
        related="company_id.payment_due_notify_enabled", readonly=False
    )
    payment_due_notify_days_first = fields.Integer(
        related="company_id.payment_due_notify_days_first", readonly=False
    )
    payment_due_notify_second_enabled = fields.Boolean(
        related="company_id.payment_due_notify_second_enabled", readonly=False
    )
    payment_due_notify_days_second = fields.Integer(
        related="company_id.payment_due_notify_days_second", readonly=False
    )
    payment_due_notify_time = fields.Float(
        related="company_id.payment_due_notify_time", readonly=False
    )
    payment_due_notify_user_ids = fields.Many2many(
        related="company_id.payment_due_notify_user_ids", readonly=False
    )
    payment_due_notify_balance_account_ids = fields.Many2many(
        related="company_id.payment_due_notify_balance_account_ids", readonly=False
    )
    # Not a plain related field: get_values()/set_values() below suggest a
    # default from the company's country when nothing is stored yet, which
    # a related field cannot do since it always recomputes from the
    # (still empty) target on every read, discarding any suggested value.
    payment_due_notify_tz = fields.Selection(
        _tz_get,
        string="Notification timezone",
        help="Timezone used to evaluate the notification time above. "
        "Never assumed from the server; set it explicitly if it is not "
        "suggested automatically when you enable this feature.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        company = self.env.company
        res["payment_due_notify_tz"] = (
            company.payment_due_notify_tz
            or company._get_payment_due_notify_default_tz()
        )
        return res

    def set_values(self):
        super().set_values()
        self.env.company.payment_due_notify_tz = self.payment_due_notify_tz
