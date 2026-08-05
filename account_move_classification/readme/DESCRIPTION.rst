This module allows classifying accounting entries (customer invoices, vendor bills,
credit notes, debit notes, and journal entries) with a free, non-mandatory
classification defined through a configuration table.

Each classification has a name, an optional code, a color (displayed as a colored
chip/badge), and can optionally be restricted to a specific company. Classifications
with no company assigned are available across all companies.

The ``Classification`` field appears in the header of every ``account.move`` form and
can be searched and grouped from the invoice list views.
