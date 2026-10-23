import { patch } from "@web/core/utils/patch";
import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { BankRecSelectCreateDialog } from "@account_accountant/components/bank_reconciliation/search_dialog/search_dialog";

// 3.12 - "Search: Journal Items to Match" dialog (opened from the
// reconciliation screen's own "Conciliar"/"Reconcile" button, which calls
// reconcileOnReconcileLine()) searches account.move.line across every
// journal/company by design (see getReconcileButtonDomain() in
// button_list.js - no journal_id term at all), since the whole point is to
// also catch a payment/receipt registered against the wrong bank journal.
// That's useful, but it means every candidate from every OTHER bank shows up
// too, which is noisy on an account that mostly settles through its own
// journal. The dialog's own search view (view_account_move_line_search_
// bank_rec_widget) already has a `journal_id` facet - this only pre-selects
// it (same mechanism the native code already uses for
// `search_default_partner_id`), still fully removable by the user from the
// search bar like any other default filter.
//
// NOT implemented by overriding reconcileOnReconcileLine() itself (an
// earlier version of this fix did exactly that, same as the native
// implementation does, and broke in production): a third-party module
// installed on at least one client (ingadhoc/odoo-argentina-ee's
// account_accountant_ux) does the exact same thing - its own full
// replacement of reconcileOnReconcileLine(), adding its own default
// filters, with no super() call either. patch() chains by wrapping, but
// since NEITHER override calls super(), whichever one happens to load
// last in the asset bundle completely replaces the other - there is no
// "both run" outcome, and no reliable way to control load order between
// two independent modules that don't know about each other. Confirmed in
// a real deployment: our own filter was silently dead code, discarded in
// favor of account_accountant_ux's version, despite patch() applying
// without any error.
//
// Instead, this wraps the single shared mechanism BOTH implementations
// (and the native one) already call identically to open the dialog -
// addDialog(), from useOwnedDialogs() - and injects the journal default
// into whatever context was already built, regardless of which
// reconcileOnReconcileLine implementation constructed it. This survives
// future upstream changes to that method's internals, and any other
// third-party override of it, as long as it still opens
// BankRecSelectCreateDialog for account.move.line - the one invariant
// every version (native, ours, account_accountant_ux's) actually shares,
// since that's the entire point of the button.
//
// Company setting (bank_statement_reconcile_dialog_default_journal,
// default True): a company with few bank journals may prefer seeing every
// candidate without the extra click to clear this filter. Exposed as a
// related field straight on account.bank.statement.line (see
// models/account_bank_statement_line.py) and added to this same kanban
// view (views/account_bank_statement_line_views.xml) so it's already part
// of statementLineData - no extra RPC needed to read it here.
patch(BankRecButtonList.prototype, {
    setup() {
        super.setup(...arguments);
        const nativeAddDialog = this.addDialog;
        this.addDialog = (dialogClass, props, options) => {
            if (
                dialogClass === BankRecSelectCreateDialog &&
                props?.resModel === "account.move.line" &&
                this.statementLineData.journal_id &&
                this.statementLineData.reconcile_dialog_default_journal &&
                !props.context?.search_default_journal_id
            ) {
                props = {
                    ...props,
                    context: {
                        ...props.context,
                        search_default_journal_id: this.statementLineData.journal_id.id,
                    },
                };
            }
            return nativeAddDialog(dialogClass, props, options);
        };
    },
});
