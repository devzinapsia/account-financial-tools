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
  meant to settle through a receipt/payment order. Enabling it stops
  automatic reconciliation (both the scheduled cron and the one
  triggered right after the CUIT match on import) from ever matching a
  statement line straight to a receivable/payable account; matching
  through an outstanding account, or falling back to a reconcile model,
  is unaffected. Disabled by default. See "Decisiones de diseño".

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
  lo que en un banco con mucho volumen muestra todo el tiempo resultados
  de otros bancos. Se precarga el filtro "Diario" con el banco que se
  está conciliando - igual que ya hace con el contacto - pero sigue
  siendo un filtro común, removible desde la barra de búsqueda.
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
  conciliación normal vía recibo/OP. Por compañía (no por diario,
  siguiendo cómo Odoo ya guarda las cuentas de pagos/cobros pendientes a
  nivel de método de pago, no de diario); desactivada por defecto para
  no cambiar el comportamiento de ninguna instalación existente.
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
