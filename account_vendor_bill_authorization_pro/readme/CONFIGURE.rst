#. Go to **Accounting ‣ Configuration ‣ Settings**, section **Vendor
   Payments**, and check **Allow pay now on vendor invoices?** (*Permitir
   pago directo en facturas de proveedores?*, from ``account_payment_pro``).
   The settings of this module only show up once it is checked.
#. In the **Vendor bill authorization bypass** setting just below it, set
   (per company):

   * **Journals that bypass authorization**: the petty cash (or similar)
     journals bills may be paid with when they are loaded. They need a
     *Manual* outgoing payment method, as the *Pay now journal* requires.
   * **Users allowed to use this bypass**: the only users who can set a pay
     now journal on a vendor bill, or confirm a bill that has one.

   Leaving the journals empty disables the bypass: the *Pay now journal*
   then works exactly as ``account_payment_pro`` defines it, for every
   user.
#. **Journal Security** (``account_journal_security``): restrictions set on
   each journal (*Advanced Settings ‣ Restrict to users*) keep applying on
   top of this module. A user restricted out of a journal (*Total*) can't
   see or pick it; a user without modification rights on it
   (*Modification*) can pick it, but confirming the bill fails, because
   the payment can't be created in that journal. Make sure the allowed
   users above also have rights on the bypass journals in Journal Security.
#. **Vendor payment authorization** (``account_payment_authorization``):
   no extra setup is needed. Payment policies don't apply to the payment
   created when a bypassed bill is confirmed, except policies marked
   *Always block*. A payment policy marked *Always block* that matches
   that payment (e.g. one conditioned on the petty cash journal) leaves
   the bill confirmed and its payment blocked in draft, so avoid such
   policies on the bypass journals. Every other payment goes through
   payment authorization as usual: payments from other journals, and
   payments from a bypass journal that settle something other than bills
   with that same pay now journal.
