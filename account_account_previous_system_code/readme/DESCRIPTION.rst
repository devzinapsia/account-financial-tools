When migrating a customer's chart of accounts from their previous system,
it is useful to keep track of the account code each account had in that
system, so it can be referenced later (mappings, reconciliations,
historical lookups, etc.).

This module adds a "Previous system account code" field to
``account.account``, searchable and available as an optional column in
the chart of accounts list. The code is free-form and optional, but when
set it must be unique among accounts sharing a company (directly, or
through a parent/child company relationship).
