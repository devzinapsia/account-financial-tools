===================================================
Autorización de facturas de proveedor - Payment Pro
===================================================

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

**Table of contents**

.. contents::
   :local:

Configuration
=============

No configuration of its own: the authorization policies are configured in
``account_vendor_bill_authorization``.

Usage
=====

Paying vendor bills with payment receipts
-----------------------------------------

Create a vendor payment receipt as usual. The debt it fills in only
includes the vendor bills that can be paid: those not requiring
authorization and those already authorized. Bills still *To authorize*
(or *Rejected*) are left out; once a bill is authorized, *Add all* picks
it up. Adding such a bill by hand is refused with an error naming it.

Paying on confirmation
----------------------

A vendor bill with a **pay now** journal is paid as soon as it is
confirmed. If the bill matches an authorization policy (so it will require
authorization), confirming it is refused: remove the pay now journal,
confirm the bill, and pay it once it is authorized. Bills that don't
require authorization keep being paid on confirmation as before.

Bug Tracker
===========

Bugs are tracked on
`GitHub Issues <https://github.com/devzinapsia/account-financial-tools/issues>`_.
In case of trouble, please check there if your issue has already been
reported.

Credits
=======

Authors
-------

* Zinapsia

Maintainers
-----------

This module is maintained by Zinapsia.

This module is part of the
`account-financial-tools <https://github.com/devzinapsia/account-financial-tools>`_
project.
