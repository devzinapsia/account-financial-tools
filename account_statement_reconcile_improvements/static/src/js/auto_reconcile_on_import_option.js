import { patch } from "@web/core/utils/patch";
import { BaseImportModel } from "@base_import/import_model";

// wizard/base_import_import.py's execute_import() reads
// options['bank_stmt_auto_reconcile_by_contact_date_amount'] to decide
// whether to run action_auto_reconcile_unassigned_by_amount_and_date() on
// the just-imported lines - see static/src/xml/auto_reconcile_on_import_option.xml
// for the checkbox. Same pattern as force_duplicate_lines_option.js, except
// this option defaults to checked (True): the placeholder value below only
// exists so the native setOption()/_onLoadSuccess() never crash writing to
// a key that doesn't exist yet - the real value always comes right after,
// either from the user's own toggle or from
// wizard/base_import_import.py's parse_preview(), which (unlike the
// duplicate-lines option) always injects an explicit value, saved or
// default, precisely so this checkbox never silently renders unchecked on
// a journal's first-ever import.
const OPTION_NAME = "bank_stmt_auto_reconcile_by_contact_date_amount";

patch(BaseImportModel.prototype, {
    setOption(optionName, value, fieldName) {
        if (optionName === OPTION_NAME && !this.importOptionsValues[optionName]) {
            this.importOptionsValues[optionName] = { value: true };
        }
        return super.setOption(optionName, value, fieldName);
    },

    _onLoadSuccess(res) {
        if (res.options && OPTION_NAME in res.options && !this.importOptionsValues[OPTION_NAME]) {
            this.importOptionsValues[OPTION_NAME] = { value: true };
        }
        return super._onLoadSuccess(res);
    },
});
