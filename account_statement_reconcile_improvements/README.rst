=============================
Mejoras a conciliación bancaria
=============================

This module improves the bank statement file import and reconciliation
workflow for Argentine banks, on top of Odoo Enterprise's own bank
statement import (``account_bank_statement_import_csv``) and bank
reconciliation widget (``account_accountant``).

Import improvements
====================

- **Column mapping remembered per journal.** Odoo's own mapping memory
  (``base_import.mapping``) is keyed only by target model, globally across
  every bank/journal - two banks that happen to reuse the same column
  header for a different meaning silently overwrite each other's saved
  mapping. This module keeps its own mapping snapshot per bank journal, so
  reimporting for the same journal reliably prefills the same mapping.
- **The imported file is always attached** to the resulting bank statement
  (``ir.attachment``), not only when using OCR/digitalization.
- **Re-importing the exact same file is blocked.** A SHA-256 of the file
  is stored on the statement (``import_file_hash``, unique per journal);
  trying to import the same file again for the same journal is rejected
  with the name/date/user of the statement that already has it.
- **Overlapping-period duplicate lines are skipped automatically.** Before
  creating statement lines, each row is checked against existing lines for
  the same journal (any statement, any reconciliation state). A row whose
  date, partner and amount match an existing line is treated as a probable
  duplicate and is not imported; the import result reports how many rows
  were skipped this way. See "Decisiones de diseño" for the exact matching
  rule and for why this doesn't offer a per-row checkbox in the preview.
- **CUIT recognition in a free-text legend column.** A new "Contact (CUIT
  in free-text legend)" field can be mapped from the bank's own
  description/legend column; if exactly one valid Argentine CUIT is found
  in the text (checksum-validated), the corresponding partner is assigned
  automatically.
- **Bank exports with leading metadata rows are handled automatically**
  (e.g. BBVA's account/period summary before the real column headers, or
  banks that interleave blank separator rows through the data) - no manual
  file editing needed before importing.

Reconciliation improvements
============================

- **Bug fix: CUIT matching against several contacts.** Assigning a partner
  from its CUIT no longer fails just because a company and its own child
  contacts (which inherit the company's VAT) all match the same number -
  only top-level contacts are considered, see "Decisiones de diseño".
- **New "Auto-reconcile unassigned" button** on the bank reconciliation
  screen: for unreconciled lines with no partner, it looks for a unique
  open invoice/payment matching on date and amount and reconciles it.
- **Deleting a bank statement no longer leaves orphaned lines** or
  invoices/payments stuck as reconciled: it now shows an explicit warning
  and, if confirmed, unreconciles every line first (reopening the matched
  invoices/payments) before deleting.
- **A general setting** ("Auto-reconciled bank statement lines", in
  Accounting settings) controls whether lines reconciled automatically
  (by the CUIT match above, by the new button, or by an
  ``account.reconcile.model`` with automatic validation) are flagged "to
  check" instead of fully reviewed. Enabled by default.

Decisiones de diseño
=====================

Estas son decisiones de producto ya tomadas para este módulo, documentadas
acá para que queden trazables:

- **Duplicado de línea de extracto**: dos líneas se consideran "el mismo
  movimiento" si coinciden en fecha, contacto e importe (mismo signo y
  moneda), sin importar si están conciliadas o si vienen de un extracto
  distinto. La comparación se hace contra el mismo diario bancario (no
  contra todos los diarios de la empresa), ya que el caso real que motiva
  esto es reimportar un período que se solapa con uno ya importado para
  esa misma cuenta.
- **CUIT con múltiples contactos**: al buscar por CUIT, se descartan
  primero los contactos con ``parent_id`` seteado (sucursales/personas de
  contacto que heredaron el CUIT de la empresa madre). Si después de ese
  filtro sigue habiendo más de una empresa con el mismo CUIT, se toma la
  de ``create_date`` más antiguo (``id`` como desempate).
- **DNI**: el reconocimiento es best-effort (no tiene dígito verificador,
  a diferencia del CUIT). La extracción está disponible como utilidad
  (``tools/ar_id_extraction.py``, cubierta por tests con casos reales de
  los extractos de ejemplo), pero **no** se usa hoy para asignar contacto
  automáticamente: ``res.partner.vat`` en Argentina normalmente guarda el
  CUIT, no un DNI suelto, y no hay un campo estándar con el que cruzarlo
  de forma confiable sin depender de configuración específica de cada
  cliente. Puede ampliarse a futuro si un cliente puntual lo necesita.
- **Ambigüedad en la columna de texto**: si aparece más de un CUIT válido
  en el texto, el contacto queda en blanco (no se adivina ni se rechaza la
  importación).
- **Conciliación automática y "a revisar"**: el parámetro general de
  Contabilidad decide si las líneas conciliadas automáticamente (por el
  match de CUIT al importar, por el botón nuevo, o por un
  ``account.reconcile.model`` con validación automática) quedan marcadas
  "a revisar" (campo nativo ``checked``/"Reviewed" de v19, heredado por
  ``account.bank.statement.line`` desde ``account.move``) en vez de
  confirmadas. Activado por defecto.
- **Borrado de extracto**: antes de borrar un extracto con líneas
  conciliadas se muestra una advertencia explícita a nivel del extracto
  (no línea por línea); si se confirma, todas sus líneas se desconcilian
  sin más preguntas.
- **Duplicado de línea sin grilla interactiva**: la fila 3.4 del pedido
  original pedía una grilla de previsualización con un checkbox
  "Importar" por fila. Implementar eso requiere reconstruir el componente
  OWL de previsualización nativo de ``base_import`` - una tarea de
  frontend bastante más grande que el resto del módulo. Por decisión
  explícita, se implementó en cambio: exclusión automática de duplicados
  por defecto + un mensaje de advertencia indicando cuántas filas se
  omitieron, con un único interruptor todo-o-nada
  (``options['bank_stmt_force_duplicate_lines']``) para forzar la
  importación completa cuando se está seguro de que no son duplicados. La
  grilla interactiva queda como posible mejora futura.

Reconciliation model vs. custom button (point 3.8 analysis)
=============================================================

``account.reconcile.model`` was evaluated as a way to implement "match by
amount and date only, no partner" natively. It doesn't cover this case:

- Its ``match_amount`` field only supports a fixed threshold or range
  ("lower/greater/between" a configured amount), not "equals whatever
  amount an existing open item happens to have".
- Candidate search against open receivable/payable journal items (the
  actual invoice/payment matching) is not part of ``account.reconcile.model``
  at all - it's a separate mechanism built into the bank reconciliation
  widget itself, and it isn't triggered without a partner on the
  statement line.

So a reconcile model cannot express "no partner, but there's a unique open
item with the same date and amount" - the new "Auto-reconcile unassigned"
button was implemented for that specific case. ``account.reconcile.model``
remains the right tool for anything based on label/amount-range/partner
rules, and this module also makes sure a reconcile model configured with
"Automated" validation still respects the "to check" setting above.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Settings** and, under the
"Bank & Cash" / vendor checks area, enable or disable **Auto-reconciled
bank statement lines ‣ Flag them as to check instead of fully reviewed**
(enabled by default).

No other configuration is required: the per-journal import mapping is
learned automatically the first time you import a file for that journal,
and the CUIT recognition works on whichever column you map to the new
"Contact (CUIT in free-text legend)" field in the import wizard.

Usage
=====

Importing a bank statement file works the same way as before (from the
bank journal, **Upload**), with these differences:

- If your bank's export has a free-text legend/description column that
  sometimes contains the counterparty's CUIT, map that column to
  **Contact (CUIT in free-text legend)** instead of (or in addition to)
  mapping a real partner column.
- If a row looks like a movement you already imported for this journal
  (same date, contact and amount), it is skipped automatically and
  reported in the import result - check the warning message if the
  number of imported lines looks lower than expected.
- Reimporting the exact same file for the same journal is rejected
  outright, with a reference to the statement that already has it.

On the bank reconciliation screen, use the new **Auto-reconcile
unassigned** button to try to match every unassigned, unreconciled line
against a unique open invoice/payment with the same date and amount.

Deleting a bank statement with reconciled lines now shows a confirmation
warning before unreconciling and removing them.

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
