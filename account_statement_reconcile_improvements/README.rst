=============================
Mejoras a conciliación bancaria
=============================

This module improves the bank statement file import and reconciliation
workflow for Argentine banks, on top of Odoo Enterprise's own bank
statement import (``account_bank_statement_import_csv``) and bank
reconciliation widget (``account_accountant``).

Import improvements
====================

- **Column mapping and file format remembered per journal.** Odoo's own
  mapping memory (``base_import.mapping``) is keyed only by target model,
  globally across every bank/journal - two banks that happen to reuse the
  same column header for a different meaning silently overwrite each
  other's saved mapping. This module keeps its own snapshot per bank
  journal instead: not just the column mapping, but also the file format
  options native Odoo never remembers at all (encoding, separator,
  decimal/thousand separator, sheet name), plus this module's own
  checkboxes below - so reimporting for the same journal reliably prefills
  everything, not just the mapping.
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
  were skipped this way, and the full per-row detail (date, amount,
  description, contact, and which existing line each one matches) is
  posted to the resulting statement's chatter. See "Decisiones de diseño"
  for the exact matching rule and for why this doesn't offer a per-row
  checkbox in the preview. If every row in the file turns out to be a
  duplicate, no empty statement is left behind either (native Odoo would
  otherwise still create one). Check **Import even if rows look like
  duplicates** in the import screen's options sidebar to force the import
  through anyway - see "Usage" for details; remembered per journal like
  everything else in this section.
- **CUIT recognition in a free-text legend column.** A new "Contact (CUIT
  in free-text legend)" field can be mapped from the bank's own
  description/legend column; if exactly one valid Argentine CUIT is found
  in the text (checksum-validated), the corresponding partner is assigned
  automatically.
- **Automatic reconciliation when contact, date and amount all match.**
  After a real import, for every line still unreconciled once
  Odoo's own native auto-reconcile step is done with it, this module looks
  for a unique open invoice/payment matching on exact date and amount -
  and, when the line already has a confirmed contact (from the CUIT match
  above, or a column mapped directly to Contact), matching that same
  partner too. Controlled by **Automatically reconcile when contact, date
  and amount match** in the import screen's options sidebar - enabled by
  default, remembered per journal. The same underlying logic is also
  available on demand from the bank reconciliation screen's own cog menu
  (see "Reconciliation improvements" below).
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
- **New "Reconcile by date and amount" entry** in the bank reconciliation
  screen's own cog/Actions menu (⚙, next to "Find Duplicate Transactions"
  when ``account_online_synchronization`` is installed): for every
  unreconciled line of the journal being reconciled (no selection needed -
  it always applies to everything currently pending), it looks for a
  unique open invoice/payment matching on date and amount - and, when the
  line already has a confirmed contact, that same partner too - and
  reconciles it. The same logic also runs automatically right after a real
  import; see "Automatic reconciliation when contact, date and amount all
  match" above.
- **Deleting a bank statement no longer leaves orphaned lines** or
  invoices/payments stuck as reconciled: it now shows an explicit warning
  and, if confirmed, unreconciles every line first (reopening the matched
  invoices/payments) before deleting.
- **A general setting** ("Auto-reconciled bank statement lines", in
  Accounting settings) controls whether a line reconciled with no
  confirmed contact backing the match - by the new button, or by an
  ``account.reconcile.model`` rule with no partner condition - is flagged
  "to check" instead of fully reviewed. A line whose partner was already
  established some other way (the CUIT match above, a reconcile.model
  rule that matched a specific partner) is reliable enough to count as
  reviewed either way. Enabled by default.

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
  esa misma cuenta. El contacto solo se usa en la comparación cuando el
  módulo lo resolvió él mismo (vía el campo de CUIT en texto libre): si el
  contacto se mapeó de otra forma (directo a Partner, o un extracto viejo
  importado antes de que este módulo existiera), no hay forma de saber con
  qué contacto quedó esa línea existente, así que la comparación cae a
  fecha+importe solamente. Es una decisión deliberada a favor de no dejar
  pasar duplicados reales (falso positivo ocasional, recuperable con el
  checkbox "Import even if rows look like duplicates" del panel de
  importación) antes que arriesgarse a no detectar uno real (que sí es un
  problema serio de datos contables).
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
- **Ambigüedad en la conciliación automática por contacto+fecha+importe**:
  cuando la línea ya tiene un contacto confirmado, la búsqueda de la
  factura/pago abierto se acota a ese mismo contacto (no a cualquier
  contacto); si aun así hay más de un movimiento abierto que coincide en
  fecha e importe para ese contacto, la línea queda sin conciliar - mismo
  criterio "sin match único, no se toca" que ya se usaba para el caso sin
  contacto. Cuando el contacto ya estaba confirmado ANTES de esta
  conciliación (CUIT en texto libre, o una columna mapeada directo a
  Contacto), la línea resultante no se marca "a revisar" - se considera lo
  suficientemente confiable. Si el contacto no estaba confirmado y esta
  acción se lo asigna como efecto colateral de conciliar, sí se marca "a
  revisar" (igual que el comportamiento previo para el botón sin contacto).
- **Duplicado de línea sin grilla interactiva**: la fila 3.4 del pedido
  original pedía una grilla de previsualización con un checkbox
  "Importar" por fila. Implementar eso requiere reconstruir el componente
  OWL de previsualización nativo de ``base_import`` - una tarea de
  frontend bastante más grande que el resto del módulo. Por decisión
  explícita, se implementó en cambio: exclusión automática de duplicados
  por defecto + una notificación (toast) persistente (``sticky``, no se
  cierra sola) con la cantidad de filas omitidas (el detalle fila por fila,
  con fecha/importe/contacto y a qué línea existente coincide cada una, va
  al chatter del extracto - una lista completa no entra legible en un
  toast), con un único interruptor todo-o-nada (checkbox "Import even if
  rows look like duplicates" en el panel de importación, recordado por
  diario) para forzar la importación completa cuando se está seguro de que
  no son duplicados. No
  se usa el canal de errores nativo de ``base_import`` (``res['messages']``)
  para esto: cada entrada ahí debe traer un rango de filas (``rows``), y
  agregar una entrada sin ese formato rompe el cliente web (visto en
  producción). La grilla interactiva queda como posible mejora futura.

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
item with the same date and amount" - the new "Reconcile by date and
amount" cog menu entry was implemented for that specific case. ``account.reconcile.model``
remains the right tool for anything based on label/amount-range/partner
rules, and this module also makes sure a reconcile model configured with
"Automated" validation still respects the "to check" setting above.

The same custom mechanism was later extended to also match on a confirmed
partner (narrowing the open-item search to that contact, instead of
requiring no partner at all) - see "Automatic reconciliation when contact,
date and amount all match" above - since ``account.reconcile.model``'s own
partner-based matching still can't express "match whatever amount an open
item for this partner happens to have", only fixed thresholds/ranges.

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
  number of imported lines looks lower than expected. The full detail
  (which existing line each skipped row matches) is on the resulting
  statement's chatter.
- Reimporting the exact same file for the same journal is rejected
  outright, with a reference to the statement that already has it.
- If you're sure the flagged rows are *not* duplicates, check **Import
  even if rows look like duplicates** in the import screen's options
  sidebar (left side, under "Use first row as header") before importing
  again. It's only shown for bank statement imports, and it's remembered
  per journal like the column mapping - only when checked, though:
  unchecking it goes back to the default (checking for duplicates).
- Right above that same checkbox is **Automatically reconcile when
  contact, date and amount match** - checked by default. With it on, right
  after a real import, every line still unreconciled (once Odoo's own
  native matching is done with it) gets one more pass: if there's a unique
  open invoice/payment with the same date and amount - and, when the line
  already has a contact, the same partner too - it gets reconciled
  automatically. Uncheck it for a specific import if you'd rather review
  and reconcile those lines by hand; like the checkbox above, the choice
  is remembered per journal.

On the bank reconciliation screen, use **Reconcile by date and amount**
(⚙ cog menu, top right) to run that same on-demand, for every unreconciled
line of the journal being reconciled (no selection needed) against a
unique open invoice/payment with the same date and amount (and the same
contact, when the line already has one).

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
