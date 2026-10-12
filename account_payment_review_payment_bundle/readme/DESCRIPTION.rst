Glue between account_payment_review and ingadhoc's l10n_ar_payment_bundle.
Installs automatically when both are installed.

A payment bundle is made of a **main payment** (the payment order the user
sees, with an amount of 0) and **linked payments**, one per payment method
(cash, check, transfer...). This module makes only the main payment
reviewable: linked payments stay out of the review circuit, its filters,
the *Payments to review* menu and the review wizard. Together with
account_payment_review_payment_pro, the **Review from amount** setting is
compared against the bundle's total.

It also fixes a crash coming from l10n_ar_payment_bundle: its list of a
bundle's linked payments was picked as the default payments list wherever
no list is forced (e.g. opening payments from the activities menu), and
showing its optional columns there raised an error (*Name 'parent' is not
defined*). That list is now only used inside the bundle form, as intended.
