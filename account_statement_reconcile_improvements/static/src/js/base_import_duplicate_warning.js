import { patch } from "@web/core/utils/patch";
import { BaseImportModel } from "@base_import/import_model";
import { ImportAction } from "@base_import/import_action/import_action";

// The duplicate-rows warning used to be sent via _bus_send('simple_notification', ...)
// from execute_import() (see wizard/base_import_import.py), but the bus is an
// asynchronous, cross-session push mechanism: it isn't guaranteed to arrive
// while this specific import screen is still open, and it gets replayed on
// bus reconnection (e.g. the browser tab regaining focus), which is exactly
// what caused the message to show up late and repeatedly instead of once,
// right after the import/test call it belongs to.
//
// _callImport() returns the raw execute_import() response before
// _executeImportStep() destructures only the keys base_import itself knows
// about, so this is the one place a custom server-added key survives to be
// read. It's stashed on the model (not shown immediately via _addMessage())
// because handleImport() below navigates away to the imported records
// (ImportAction.openRecords()) right after a successful real import with at
// least one imported row - an in-page message on the about-to-be-destroyed
// import screen would never be seen, same failure mode as the bus but for a
// different reason. notification.add() is the one mechanism, also used
// natively for "N records successfully imported", that survives that
// navigation: it's rendered by a persistent, top-level service, not the
// import screen's own component tree.
patch(BaseImportModel.prototype, {
    async _callImport(dryrun, args) {
        const res = await super._callImport(dryrun, args);
        if (res) {
            this.bankStmtDuplicateWarning = res.bank_stmt_duplicate_warning || null;
        }
        return res;
    },
});

patch(ImportAction.prototype, {
    async handleImport(isTest = true) {
        await super.handleImport(...arguments);
        if (this.model.bankStmtDuplicateWarning) {
            this.notification.add(this.model.bankStmtDuplicateWarning, {
                type: "warning",
                sticky: true,
            });
            this.model.bankStmtDuplicateWarning = null;
        }
    },
});
