``account_vendor_bill_authorization`` prevents paying a confirmed vendor
bill until it is authorized, when it matches an authorization policy.

ingadhoc's ``account_payment_pro`` changes how vendor bills are paid: a
payment receipt automatically fills in all the open debt of the vendor,
and a bill can be paid on confirmation through its **pay now** journal.
This bridge module applies the vendor bill authorization rules to that
flow too:

* payment receipts leave out the bills that can't be paid yet (pending
  authorization or rejected), both when filling in the vendor's debt and
  when adding it again with *Add all*;
* such a bill can't be added to a payment receipt by hand either;
* a bill that requires authorization can't be confirmed with a pay now
  journal, since it would be paid on confirmation, before being
  authorized.

It installs automatically once both ``account_vendor_bill_authorization``
and ``account_payment_pro`` are present.
