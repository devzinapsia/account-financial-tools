Glue between account_payment_review and ingadhoc's l10n_ar_payment_bundle.
Installs automatically when both are installed.

A payment bundle is made of a **main payment** (the payment order the user
sees, with an amount of 0) and **linked payments**, one per payment method
(cash, check, transfer...). This module makes only the main payment
reviewable: linked payments stay out of the review circuit, its filters,
the *Payments to review* menu and the review wizard. Together with
account_payment_review_payment_pro, the **Review from amount** setting is
compared against the bundle's total.
