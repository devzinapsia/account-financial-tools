import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { FormController } from "@web/views/form/form_controller";

// The actual slow part of deleting a statement with reconciled lines isn't
// the list view's own confirmation dialog (see account_tree_delete_fix.js) -
// that one exits almost immediately through a RedirectWarning, before any
// real unreconciliation work starts (account_bank_statement.py's own
// unlink()). The real work only happens once "Delete anyway" is clicked on
// THIS wizard (account.bank.statement.unlink.wizard, opened by that
// RedirectWarning) - and native Odoo's only feedback for an object-type
// button's RPC is disabling every button in the dialog, with no spinner or
// message at all, easy to miss entirely on a delete that can take a while
// for a statement with thousands of reconciled lines (confirmed: this is
// the actual step a user reported seeing no feedback on).
patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        if (this._isUnlinkWizardConfirm(clickParams)) {
            this.env.services.ui.block({
                message: _t("Deleting bank statement(s)..."),
            });
        }
        return super.beforeExecuteActionButton(clickParams);
    },

    async afterExecuteActionButton(clickParams) {
        if (this._isUnlinkWizardConfirm(clickParams)) {
            this.env.services.ui.unblock();
        }
        return super.afterExecuteActionButton(clickParams);
    },

    _isUnlinkWizardConfirm(clickParams) {
        return (
            this.props.resModel === "account.bank.statement.unlink.wizard" &&
            clickParams.name === "action_confirm_unlink"
        );
    },
});
