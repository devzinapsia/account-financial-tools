Replaces a manual process of assigning an activity to each payable
document and running a scheduled action to notify by email or chat: this
module automates the whole cycle.

It watches every posted, unreconciled journal item with a payable account
(``account_type = liability_payable``), a vendor contact, and a due date
-- vendor bills, vendor credit notes, and manual entries (e.g. VAT
payable) alike, whether or not they use fiscal documents. Before each
such item's due date, it notifies a configured list of users, respecting
each user's own notification preference (email or internal notification),
exactly like the manual process it replaces.
