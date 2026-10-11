from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _review_amount(self):
        """Under account_payment_pro the amount the user thinks of as "the
        payment order's amount" is payment_total: the payment itself plus
        write-off and, with l10n_ar_tax, withholdings -- and, for a
        l10n_ar_payment_bundle main payment (whose own amount is 0), the sum
        of its linked payments. It's expressed in the debt currency, so
        convert it to company currency to compare it with the setting.
        """
        self.ensure_one()
        if not self.use_payment_pro:
            return super()._review_amount()
        company = self.company_id
        currency = self.destination_currency_id or self.currency_id
        amount = abs(self.payment_total)
        if currency == company.currency_id:
            return amount
        return currency._convert(amount, company.currency_id, company, self.date or fields.Date.context_today(self))
