Glue module between ``account_translation_improvements`` and
``account_payment``, installed automatically when both are installed.

``account_payment`` hides the invoice form's "Pay" buttons while the
invoice has an authorized online transaction that hasn't been captured or
voided yet, so a manual payment can't be registered on top of it.
``account_translation_improvements`` shows a "Collect" button instead of
"Pay" on customer documents; this module applies that same rule to the
"Collect" buttons.

It's a separate module so that ``account_translation_improvements`` only
depends on ``account``.
