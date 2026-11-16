import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { ImportRecords } from "@base_import/import_records/import_records";

// The cog menu's generic "Import records" entry (shown on the bank
// reconciliation widget too) opens the plain base_import screen on
// account.bank.statement.line. Unlike the journal dashboard's "Import File"
// upload, it never sends the 'bank_stmt_import' option, so none of this
// module's import improvements run (duplicate filter, CUIT resolution,
// day-first dates, per-journal mapping) - nor native ones keyed on it
// (debit/credit/cumulative balance columns). Rather than supporting a
// second import path, block it and point the user to the right one.
const STATEMENT_LINE_MODEL = "account.bank.statement.line";

patch(ImportRecords.prototype, {
    importRecords() {
        if (this.env.searchModel.resModel !== STATEMENT_LINE_MODEL) {
            return super.importRecords(...arguments);
        }
        this.env.services.dialog.add(AlertDialog, {
            title: _t("Import a bank statement"),
            body: _t(
                "Bank statements can't be imported from this option. To do so, go to Accounting > Dashboard and, on the bank journal's card, click \"Import File\": it is the only valid option for importing transactions to use in the bank reconciliation."
            ),
        });
    },
});
