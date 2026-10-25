Nothing to do by hand: once a rule exists, the copies are added
automatically.

**Outgoing emails.** When a document is sent (invoice sending wizard,
receipt / purchase order email, background sending, reminders), or,
with the *All communication* scope, when a message is sent to the
customer or vendor from the chatter:

* the customer or vendor receives a single email with the rule's
  addresses in ``Cc``, and the ``Bcc`` addresses receive it without
  appearing anywhere;
* addresses already in ``To`` are removed from Cc / Bcc, and an address
  both in Cc and Bcc stays in Cc only;
* internal users in Cc / Bcc who also follow the record receive only
  that copy, not a second notification;
* the Cc addresses show in the message's delivery information (envelope
  icon) in the chatter; the Bcc addresses do not.

Copies are never added to internal notes, automatic messages (tracking,
status changes, payment registered), messages without an external
recipient, nor to messages of any other model (contacts, manual journal
entries...) even when they attach the transaction's PDF. An invoice
opened from *Accounting ‣ Journal Entries* is the same record, so it is
covered.

**Incoming emails** (*All communication* scope only). When an email
reaches the chatter of a transaction (a reply to its reply-to), it is
forwarded to the rule's Cc and Bcc addresses, whatever the sender.
Addresses that already received the original email are skipped, Bcc
addresses are never exposed (when there is no Cc, each Bcc address
receives its own email), and replying to the forward goes back to the
record's chatter.

Rules are resolved as superuser: users without access to the rules still
send with the copies. A rule with an invalid condition is ignored (and
logged) instead of blocking the sending; archived users or users without
an email are skipped and logged.
