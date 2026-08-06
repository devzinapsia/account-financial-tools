This module adds an **Agreed payment method** field to vendor bills and vendor
credit notes, letting you record the payment method agreed with the vendor
(for example, bank transfer, cash, or credit card).

The payment method is selected from a configurable table with its own ABM
(create, read, update, delete), so the list of available methods can be
extended or edited without a code change. Seven common methods are loaded
by default.

The field only appears on purchase documents (vendor bills and refunds) and
is editable only while the document is in draft state.
