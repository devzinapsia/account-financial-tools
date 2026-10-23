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
- **Bug fix: large files (over Odoo's row-batch limit) failed on their
  own second batch.** Odoo's own import wizard splits a file past ~2000
  rows into several background calls on the same wizard, one per
  row-range - every one of those calls hashes the same full original
  file, not just its own slice. Only the first batch now claims the
  file-hash guard above; a later batch of the very same import no longer
  collides with the statement its own first batch just created.
- **Bug fix: a large file's own later batches could flag hundreds of
  their own rows as false duplicates.** Each batch commits its own rows
  before the next one runs, so by the time batch 2 starts, batch 1's
  rows already count as "existing lines" for the probable-duplicate
  check below - any row that merely happens to share date+amount with
  one of batch 1's own rows (common on a real statement full of
  recurring round amounts - bank fees, standard transfers) got wrongly
  skipped, in bulk, on every batch past the first. Rows from an earlier
  batch of the very same import are now excluded from that comparison;
  a genuinely separate, later re-import of an overlapping period is
  still caught.
- **Overlapping-period duplicate lines are skipped automatically.** Before
  creating statement lines, each row is checked against existing lines for
  the same journal (any statement, any reconciliation state). A row whose
  date, partner and amount match an existing line is treated as a probable
  duplicate and is not imported; the import result reports how many rows
  were skipped this way. See "Decisiones de diseño" for the exact matching
  rule and for why this doesn't offer a per-row checkbox in the preview.
  If every row in the file turns out to be a duplicate, no empty statement
  is left behind either (native Odoo would otherwise still create one).
  Check **Import even if rows look like duplicates** in the import
  screen's options sidebar to skip this check for a specific import.
- **CUIT recognition in a free-text legend column.** A new "Contact (CUIT
  in free-text legend)" field can be mapped from the bank's own
  description/legend column; if exactly one valid Argentine CUIT is found
  in the text (checksum-validated), the corresponding partner is assigned
  automatically.
- **Bug fix: a transfer between the company's own bank accounts could get
  the company itself assigned as the line's contact.** The bank's own
  export often names the account holder (the company itself) rather than
  a real counterpart on this kind of movement - if that CUIT happened to
  match, the line ended up with its own company as "contact", which is
  never a meaningful result and broke every feature that filters by
  contact afterwards (the counterpart journal item for a transfer
  typically has no partner at all). No company's own CUIT, in any
  company of the database, is matched anymore.
- **Performance: large-file CUIT matching and duplicate-row detection no
  longer scale with the number of rows.** Both used to run one full
  database query per row (a full scan of every contact with a CUIT, for
  the former); a 2000-row batch meant 2000 repeats of the same query.
  Both now run once per batch instead.
- **CUIT recognition when the legend column is also the line's own label.**
  Some banks (e.g. BBVA) have no separate legend/description column at
  all - the one column that IS the transaction's own label ("Concepto")
  is also the only place the CUIT shows up. Mapping that column to the
  field above would discard the label text entirely (it gets replaced by
  the resolved contact). A second field, "Label + Contact (CUIT in
  free-text legend)", keeps the column's text as the line's label *and*
  resolves the contact from that same text.
- **Bank exports with leading metadata rows are handled automatically**
  (e.g. BBVA's account/period summary before the real column headers, or
  banks that interleave blank separator rows through the data) - no manual
  file editing needed before importing.
- **Bug fix: a large import's progress bar showed nothing at all during
  its first batch.** Odoo's own import screen only displays its batch
  counter/progress bar once the *second* batch starts; a file that needs
  just one or two batches (anywhere up to 4000 rows at the default
  2000-row batch size) could spend several minutes - the time it takes to
  process a real bank statement with thousands of lines - showing nothing
  behind the loading overlay, looking frozen. The counter and progress
  bar (still starting at 0%) now show from the very first batch.
- **Bug fix: an ambiguous date column could get its day and month
  swapped, with no error at all.** Odoo's own date-format auto-detection
  tries every month-first pattern (``%m-%d-%Y``, US-style) before its
  day-first equivalent (``%d-%m-%Y``) - when a column's sample values are
  genuinely ambiguous (every day value happens to be 12 or below, not
  unlikely on a short statement or one spanning less than half a month),
  both match and the month-first guess silently wins. Confirmed against a
  real BBVA export where every single row fell in that window: 2 de
  septiembre was imported as 9 de febrero, for the whole file, with no
  warning anywhere. Every bank statement this module exists for is
  Argentine (always day-first) - the same candidate list is now tried
  day-first, well before its month-first equivalent, specifically for
  this import (a plain data import elsewhere in Odoo - contacts,
  products, anything unrelated to bank statements - is unaffected). A
  genuinely unambiguous column (any day value above 12 anywhere in the
  sample) was never affected either way.

Reconciliation improvements
============================

- **Bug fix: CUIT matching against several contacts.** Assigning a partner
  from its CUIT no longer fails just because a company and its own child
  contacts (which inherit the company's VAT) all match the same number -
  only top-level contacts are considered, see "Decisiones de diseño".
- **New "Reconcile by date and amount" entry** in the bank reconciliation
  screen's own cog/Actions menu (⚙, next to "Find Duplicate Transactions"
  when ``account_online_synchronization`` is installed): for every
  unreconciled line of the journal being reconciled with no partner (no
  selection needed - it always applies to everything currently pending),
  it looks for a unique open invoice/payment matching on date and amount
  and reconciles it.
- **Deleting a bank statement no longer leaves orphaned lines** or
  invoices/payments stuck as reconciled: it now shows an explicit warning
  and, if confirmed, unreconciles every line first (reopening the matched
  invoices/payments) before deleting.
- **A general setting** ("Account reconciliation", in Accounting settings
  ‣ Bank & Cash) controls whether a line reconciled with no confirmed
  contact backing the match - by the new button, or by an
  ``account.reconcile.model`` rule with no partner condition - is flagged
  "to check" instead of fully reviewed. A line whose partner was already
  established some other way (the CUIT match above, a reconcile.model
  rule that matched a specific partner) is reliable enough to count as
  reviewed either way. Enabled by default.
- **New "Create Bill" entry** in the bank reconciliation screen's own
  "..." dropdown, right below "Upload Bills": opens a blank vendor bill
  (pre-filled with the line's contact and date) for a purchase the user
  has no file for yet. Unlike "Upload Bills", this never requires
  attaching a document first.
- **New setting: "Only auto-reconcile through outstanding accounts".**
  Odoo's own automatic bank reconciliation can match a statement line
  directly against an open invoice/bill's receivable/payable account,
  skipping the outstanding payment/receipt ("cuenta puente") account
  entirely - wrong for a bookkeeping flow where bank lines are only ever
  meant to settle through a receipt/payment order. Enabled by default,
  it stops automatic reconciliation (the scheduled cron, the one triggered
  right after the CUIT match on import, and the "Reconcile by date and
  amount" button/cog-menu entry above) from ever matching a statement line
  straight to a receivable/payable account; matching through an
  outstanding account, or falling back to a reconcile model, is
  unaffected. Disable it for a company that settles bank lines directly
  against invoices/bills instead. See "Decisiones de diseño".

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
- **CUIT propio excluido de la resolución de contacto**: el ``res.partner``
  de ``res.company.partner_id`` - de cualquier empresa de la base, no solo
  la activa, ya que una transferencia entre empresas del mismo grupo puede
  traer el CUIT de cualquiera de ellas - nunca se asigna como contacto de
  una línea, aunque su CUIT aparezca en el texto libre. Caso típico: una
  transferencia entre cuentas bancarias propias, donde el extracto nombra
  al titular de la cuenta (la propia empresa) en vez de una contraparte
  real. Asignar la propia empresa como contacto nunca tiene sentido
  (nunca se le va a emitir un recibo/OP a uno mismo) y además rompe el
  filtrado por contacto en otras partes del módulo, porque la línea
  contrapartida de una transferencia normalmente no tiene contacto
  asignado - filtrar por el contacto incorrecto oculta el match correcto
  en vez de acotarlo.
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
- **Bug fix: campo CUIT duplicado en el selector de columnas**: los dos
  campos virtuales de CUIT aparecían también, de forma espuria, anidados
  bajo "Estados de cuenta /" en el selector de mapeo de columnas.
  ``account.bank.statement.line`` está unificado con ``account.move``
  (herencia por delegación desde v17), que trae su propio campo One2many
  de vuelta a ``account.bank.statement.line`` (``statement_line_ids``,
  "Estados de cuenta"); al recorrerlo, el armado del árbol de campos de
  ``base_import`` vuelve a invocarse a sí mismo sobre el mismo modelo, y
  sin un control de profundidad nuestros campos se agregaban de nuevo en
  esa llamada recursiva. Corregido limitando el agregado a la llamada de
  nivel superior real (``depth == FIELDS_RECURSION_LIMIT``).
- **Bug fix: "Reconcile by date and amount" no refrescaba la pantalla.**
  Tras reconciliar, las líneas quedaban mostrándose como pendientes hasta
  navegar a otra pantalla y volver. La acción de cliente
  ``soft_reload`` usada originalmente llama a ``action.restore()`` de
  Odoo, pensada para una navegación "volver atrás" barata - puede reusar
  el estado ya exportado/cacheado del controlador en vez de pedir datos
  de nuevo al servidor. Corregido llamando directamente a
  ``this.env.model.load()`` (el mismo mecanismo que ya usa
  ``kanban_renderer.js`` de este widget tras su propio flujo de
  quick-create), que fuerza un refetch real y también vuelve a disparar
  el hook ``onRootLoaded`` que recalcula los totales/contadores del
  diario.
- **Filtro por diario precargado en "Buscar: Apuntes Contables para
  Conciliar"**: el diálogo nativo busca candidatos en todos los diarios
  (a propósito, para detectar pagos registrados en el banco equivocado),
  lo que en un cliente con muchos bancos (p. ej. 25) muestra todo el
  tiempo resultados de otros bancos. Se precarga el filtro "Diario" con
  el banco que se está conciliando - igual que ya hace con el contacto -
  pero sigue siendo un filtro común, removible desde la barra de
  búsqueda. Configurable por compañía ("Pre-filter the journal in the
  reconciliation search dialog", activado por defecto); para un cliente
  con pocos bancos, donde los resultados de otros diarios nunca
  molestan, se puede desactivar.
  **Bug fix: el filtro quedaba completamente inerte en un cliente con
  `ingadhoc/odoo-argentina-ee`'s ``account_accountant_ux`` instalado** -
  ese módulo también reemplaza el mismo método del botón "Conciliar"
  (sin llamar a la implementación nativa), y como la primera versión de
  este fix hacía lo mismo, cualquiera de los dos que cargara último
  pisaba por completo al otro. Corregido enganchando el mecanismo común
  que ambas implementaciones usan para abrir el diálogo, en vez de
  reemplazar el método entero - ver "Decisiones de diseño".
- **"Create Bill" sin adjunto**: la propia opción "Upload Bills" de
  ``account_accountant`` (``create_document_from_attachment``) siempre
  exige al menos un adjunto - no tiene una variante sin archivo. Por eso
  se agregó un botón separado que crea una factura de proveedor en blanco
  (sin líneas, sin conciliar contra el movimiento) para completarla a
  mano; la conciliación posterior es la misma que la de cualquier otra
  factura pendiente.
- **Conciliación automática y "a revisar"**: el parámetro general de
  Contabilidad decide si las líneas conciliadas automáticamente (por el
  match de CUIT al importar, por el botón nuevo, o por un
  ``account.reconcile.model`` con validación automática) quedan marcadas
  "a revisar" (campo nativo ``checked``/"Reviewed" de v19, heredado por
  ``account.bank.statement.line`` desde ``account.move``) en vez de
  confirmadas. Activado por defecto.
- **"Only auto-reconcile through outstanding accounts"**: Odoo concilia
  automáticamente una línea de extracto apenas tiene contacto asignado
  (``account_accountant``'s ``_try_auto_reconcile_statement_lines()`` -
  el mismo mecanismo que hace inútil, por redundante, cualquier checkbox
  propio para "conciliar por contacto+fecha+importe al importar"; ver el
  historial de este módulo). Ese matcheo nativo, al no encontrar un
  comprobante en la cuenta puente (pagos/cobros pendientes), cae a
  buscar directamente en cualquier cuenta conciliable - incluidas las de
  deudores/proveedores de las facturas - lo cual rompe un circuito
  contable donde el extracto bancario solo debería conciliar contra un
  recibo/orden de pago (que sí usan la cuenta puente), nunca directo
  contra la factura. La opción filtra las cuentas de tipo
  ``asset_receivable``/``liability_payable`` de los dos únicos puntos
  nativos que buscan fuera de las cuentas puente
  (``_handle_reconciliation_matching_amount``/``_match_accounts_query``
  con ``match_journal``/``outstanding_account`` en ``False``) - nunca
  del paso que sí busca en las cuentas puente, para no romper la
  conciliación normal vía recibo/OP. El botón propio "Reconcile by date
  and amount" (``action_auto_reconcile_unassigned_by_amount_and_date``)
  es un punto de entrada aparte - no pasa por esos dos métodos nativos,
  arma su propia búsqueda directa de ``account.move.line`` - así que
  respeta la misma opción por separado, excluyendo las mismas cuentas de
  su propio dominio de búsqueda cuando la compañía la tiene activada.
  Por compañía, no por diario/método
  de pago: separarlo por diario exigiría duplicar una porción mucho más
  grande de la orquestación nativa de ``_try_auto_reconcile_statement_lines``
  (``_match_accounts_query`` no devuelve resultado, deja la consulta SQL
  en el cursor para que quien lo llama haga ``fetchall()`` - llamarlo dos
  veces por separado rompe ese contrato), bastante más fragilidad para un
  caso acotado: un REC/OP ya cargado siempre le gana a la factura (la
  conciliación nativa agota primero todo el paso de cuentas puente, para
  *todas* las líneas del lote, antes de siquiera intentar el paso de
  facturas), así que el bug solo aparece cuando todavía no hay ningún
  recibo/OP cargado - no hay conflicto real entre ambos que justifique esa
  complejidad adicional. Activada por defecto: la mayoría de los clientes
  de Zinapsia trabajan con cuenta puente; se desactiva puntualmente en la
  compañía que concilie extractos directo contra factura.
- **Borrado de extracto**: antes de borrar un extracto con líneas
  conciliadas se muestra una advertencia explícita a nivel del extracto
  (no línea por línea); si se confirma, todas sus líneas se desconcilian
  sin más preguntas.
- **Bug fix: borrar un extracto grande (miles de líneas conciliadas) podía
  fallar con un error de acceso ajeno al propio extracto**, en una base
  con varias empresas. ``is_reconciled`` es un campo computado que, para
  miles de líneas, hace que el ORM precargue (*prefetch*) de paso un lote
  amplio e incidental de otros ``account.move`` - en una base con varias
  empresas, ese lote puede incluir por pura coincidencia un registro de
  una empresa que el usuario no tiene activa en ese momento, lo que frena
  toda la lectura con un error de acceso totalmente ajeno al extracto que
  se quiere borrar (confirmado contra un caso real: el registro que
  aparecía en el error no tenía ninguna relación con el extracto). El
  chequeo de líneas conciliadas y la desconciliación ahora se hacen con
  ``sudo()`` para esto específicamente - no expone datos nuevos al
  usuario, solo evita ese ruido incidental en una operación sobre sus
  propios registros.
- **Bug fix: borrar extractos desde la lista "Estados de cuenta
  bancarios" podía fallar directamente, sin llegar siquiera al servidor**
  - en un cliente cuya vista de esa lista fue personalizada (p. ej. por
  Studio) para reusar el ``js_class="account_tree"`` nativo (pensado
  para listas de ``account.move`` - facturas, asientos - no para
  ``account.bank.statement``). Ese controlador nativo, antes de pedir
  confirmación, siempre llama a
  ``account.move.check_move_sequence_chain()`` con los ids de lo
  seleccionado EN LA VISTA ACTUAL, sin verificar que el modelo
  realmente sea ``account.move`` - al reusarlo para extractos, termina
  chequeando esos mismos números de id como si fueran asientos
  contables. Como ambas tablas comparten la misma secuencia global de
  ids de Postgres, esos números pueden coincidir por pura casualidad
  con un asiento real de otra empresa (error de acceso) o con ninguno
  (``Registro faltante``), sin ninguna relación con el extracto que se
  quiere borrar - confirmado contra un caso real. No es un bug de este
  módulo ni de Odoo nativo en su uso previsto, sino de esa reutilización
  puntual del ``js_class``; se corrige acá para que esa pantalla
  funcione sea cual sea el ``js_class`` que termine usando.
- **Borrado de extracto(s) sin feedback visual**: ni el diálogo de
  confirmación de la lista ni el botón "Delete anyway" del asistente de
  arriba (para un extracto con líneas conciliadas - el caso real que
  realmente tarda, desconciliando miles de líneas una por una) mostraban
  nada mientras la respuesta del servidor volvía - el único feedback
  nativo de Odoo para ese botón es dejar los botones del diálogo
  deshabilitados, sin spinner ni mensaje, fácil de no notar en un borrado
  que puede tardar. Se agregó el mismo overlay de bloqueo genérico que
  usa Odoo para otras acciones largas, en ambos puntos, visible desde el
  instante en que se confirma el borrado (no después de una
  demora/estimación).
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

**Table of contents**

.. contents::
   :local:

Configuration
=============

Go to **Accounting ‣ Configuration ‣ Settings** and, under the
"Bank & Cash" area, enable or disable **Account reconciliation** (leave
statement lines reconciled automatically - either on import or by a
reconciliation model - flagged to check; enabled by default).

In the same area, disable **Only auto-reconcile through outstanding
accounts** if bank statement lines in this company do *not* always
settle through a receipt/payment order - leave it enabled (the default)
for a company whose bookkeeping always goes through one, so Odoo's own
automatic reconciliation never matches a statement line straight to an
invoice/bill instead.

Also in the same area, disable **Pre-filter the journal in the
reconciliation search dialog** for a company with few enough bank
journals that seeing every candidate from every bank in "Search: Journal
Items to Match" is never in the way. Enabled by default - useful for a
company with many bank journals.

No other configuration is required: the per-journal import mapping is
learned automatically the first time you import a file for that journal,
and the CUIT recognition works on whichever column you map to the new
"Contact (CUIT in free-text legend)" field - or, for banks with no
separate legend column (e.g. BBVA's "Concepto"), the "Label + Contact
(CUIT in free-text legend)" field - in the import wizard.

Usage
=====

Importing a bank statement file works the same way as before (from the
bank journal, **Upload**), with these differences:

- If your bank's export has a free-text legend/description column that
  sometimes contains the counterparty's CUIT, map that column to
  **Contact (CUIT in free-text legend)** instead of (or in addition to)
  mapping a real partner column.
- If your bank's export has no separate legend column - the transaction's
  own label is the only place the CUIT shows up (e.g. BBVA's "Concepto") -
  map that column to **Label + Contact (CUIT in free-text legend)**
  instead: it keeps the column's text as the line's label and resolves
  the contact from it at the same time.
- If a row looks like a movement you already imported for this journal
  (same date, contact and amount), it is skipped automatically and
  reported in the import result - check the warning message if the
  number of imported lines looks lower than expected.
- Reimporting the exact same file for the same journal is rejected
  outright, with a reference to the statement that already has it.
- If you're sure the flagged rows are *not* duplicates, check **Import
  even if rows look like duplicates** in the import screen's options
  sidebar (left side, under "Use first row as header") before importing
  again. It's only shown for bank statement imports, and it's remembered
  per journal like the column mapping - only when checked, though:
  unchecking it goes back to the default (checking for duplicates).

On the bank reconciliation screen, use **Reconcile by date and amount**
(⚙ cog menu, top right) to try to match every unassigned, unreconciled
line of the journal being reconciled against a unique open
invoice/payment with the same date and amount.

Deleting a bank statement with reconciled lines now shows a confirmation
warning before unreconciling and removing them.

On the bank reconciliation screen, use **Create Bill** (in the "..."
dropdown, below "Upload Bills") to open a blank vendor bill for a line you
don't have a receipt/invoice file for yet, instead of attaching a
placeholder file just to get past "Upload Bills".

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
