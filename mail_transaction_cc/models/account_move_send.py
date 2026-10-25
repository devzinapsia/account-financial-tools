from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _send_mail(self, move, mail_template, **kwargs):
        """Every invoice sending (single wizard, batch wizard and background
        cron) goes through here: flag it as the sending of the document."""
        move = move.with_context(mail_transaction_cc_document=True)
        return super(
            AccountMoveSend, self.with_context(mail_transaction_cc_document=True)
        )._send_mail(move, mail_template, **kwargs)
