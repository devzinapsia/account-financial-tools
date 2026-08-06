This module adds an **Estimated Payment Date** field to vendor bills and vendor
credit notes, independent of the accounting **Due Date** (``invoice_date_due``).

It is meant to record when a vendor bill is actually expected to be paid (for
example, based on internal cash-flow planning), which can differ from the
contractual due date calculated from payment terms.

The field only appears on purchase documents (vendor bills and refunds) and is
editable only while the document is in draft state.
