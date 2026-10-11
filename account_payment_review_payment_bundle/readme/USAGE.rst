Review the bundle's main payment as any other payment. Its linked
payments never show a review status.

What the payment lists show for a bundle
----------------------------------------

Only the main payment is listed (ingadhoc's *Main Payments* filter, and
the *Payments to review* menu, leave the linked payments out). On that
row:

* **Journal** and **Payment method** show the bundle's own ones
  (*Multiple payments* / *Payment multiple*), not the actual payment
  methods used (cash, checks, transfers...).
* **Amount** shows 0, since the main payment has no amount of its own;
  the **Payment total** column (added by account_payment_pro) shows the
  real total, which is also what the review wizard shows.

To see which payment methods a bundle used, open it and check its
**Payments** tab. This also means the standard *Journal* / *Payment
method* filters and group-bys don't find a bundle by the payment methods
it was paid with, e.g. "payment orders paid with checks".

Payments made with a single payment method (no bundle) show their real
journal and payment method as usual.
