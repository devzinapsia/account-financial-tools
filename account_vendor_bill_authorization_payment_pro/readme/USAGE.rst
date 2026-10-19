Paying vendor bills with payment receipts
=========================================

Create a vendor payment receipt as usual. The debt it fills in only
includes the vendor bills that can be paid: those not requiring
authorization and those already authorized. Bills still *To authorize*
(or *Rejected*) are left out; once a bill is authorized, *Add all* picks
it up. Adding such a bill by hand is refused with an error naming it.

Paying on confirmation
======================

A vendor bill with a **pay now** journal is paid as soon as it is
confirmed. If the bill matches an authorization policy (so it will require
authorization), confirming it is refused: remove the pay now journal,
confirm the bill, and pay it once it is authorized. Bills that don't
require authorization keep being paid on confirmation as before.
