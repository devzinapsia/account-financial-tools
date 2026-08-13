Some users can load vendor bills and register payments for them, but
certain payments should not be confirmed without another user's approval
first -- for example, payments above a given amount, payments using a
sensitive payment method, or payments for bills with a particular
classification.

This module adds configurable **payment authorization schemes**. Each
scheme defines a set of conditions (invoice classification, vendor,
payment method, minimum amount) and a list of users allowed to authorize
a vendor payment matching those conditions. When a user tries to confirm
a vendor payment that matches at least one scheme, and that user is not
themselves listed as an authorizer on any matching scheme, the payment is
held in a "To authorize" state instead of being confirmed, and an
activity is created for each authorized user so they can review and
approve or reject it.

This feature only applies to a payment covering a single vendor bill,
created through the standard "Register Payment" wizard. Payments for
customers, internal transfers, and grouped payments covering more than
one bill are never affected.
