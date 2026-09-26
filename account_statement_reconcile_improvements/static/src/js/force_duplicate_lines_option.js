import { patch } from "@web/core/utils/patch";
import { BaseImportModel } from "@base_import/import_model";

// wizard/base_import_import.py's _filter_out_duplicate_lines already reads
// options['bank_stmt_force_duplicate_lines'] to skip the duplicate check
// entirely, but nothing ever exposed a way to turn it on from the import
// screen - see static/src/xml/force_duplicate_lines_option.xml for the
// checkbox. BankStatementCSVImportModel (account_bank_statement_import_csv)
// overrides init() without calling super(), so this key can't be seeded
// there the way that module seeds its own 'bank_stmt_import' key.
const OPTION_NAME = "bank_stmt_force_duplicate_lines";

patch(BaseImportModel.prototype, {
    // Lazily creates the key the first time the checkbox is toggled by
    // hand - works regardless of which of the two model classes above is
    // actually instantiated, since neither overrides setOption().
    setOption(optionName, value, fieldName) {
        if (optionName === OPTION_NAME && !this.importOptionsValues[optionName]) {
            this.importOptionsValues[optionName] = { value: false };
        }
        return super.setOption(optionName, value, fieldName);
    },

    // Prefills the checkbox from the per-journal saved profile
    // (wizard/base_import_import.py's parse_preview() override) the first
    // time the wizard loads a file for a journal that already has a
    // remembered value - before the user has toggled anything themselves
    // in this session, so the key doesn't exist yet and _onLoadSuccess()'s
    // own "if (this.importOptionsValues[key])" guard would otherwise skip
    // applying it.
    _onLoadSuccess(res) {
        if (res.options && OPTION_NAME in res.options && !this.importOptionsValues[OPTION_NAME]) {
            this.importOptionsValues[OPTION_NAME] = { value: false };
        }
        return super._onLoadSuccess(res);
    },
});
