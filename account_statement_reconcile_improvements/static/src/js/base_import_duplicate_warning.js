import { patch } from "@web/core/utils/patch";
import { BaseImportModel } from "@base_import/import_model";

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
// read - relaying it into _addMessage() reuses base_import's own reliable,
// synchronous, in-page message area (the same one used for "Everything
// seems valid." and the blocking-error messages).
patch(BaseImportModel.prototype, {
    async _callImport(dryrun, args) {
        const res = await super._callImport(dryrun, args);
        if (res && res.bank_stmt_duplicate_warning) {
            this._addMessage("warning", [res.bank_stmt_duplicate_warning]);
        }
        return res;
    },
});
