Glue between account_payment_review and ingadhoc's account_payment_pro.
Installs automatically when both are installed.

Under account_payment_pro the amount that matters for a payment order is
its total (``payment_total``): the payment itself plus write-off and,
with l10n_ar_tax, withholdings. This module makes the **Review from
amount** setting compare against that total, converted to company
currency, instead of the payment's own amount. It also shows that total
in the review wizard.
