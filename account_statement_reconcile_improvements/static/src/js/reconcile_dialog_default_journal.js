import { patch } from "@web/core/utils/patch";
import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { BankRecSelectCreateDialog } from "@account_accountant/components/bank_reconciliation/search_dialog/search_dialog";
import { _t } from "@web/core/l10n/translation";

// 3.12 - "Search: Journal Items to Match" dialog (opened from "Establecer
// cuenta" / the line-matching search button) searches account.move.line
// across every journal/company by design (see getReconcileButtonDomain() in
// button_list.js - no journal_id term at all), since the whole point is to
// also catch a payment/receipt registered against the wrong bank journal.
// That's useful, but it means every candidate from every OTHER bank shows up
// too, which is noisy on an account that mostly settles through its own
// journal. The dialog's own search view (view_account_move_line_search_
// bank_rec_widget) already has a `journal_id` facet - this only pre-selects
// it (same mechanism the native code already uses for
// `search_default_partner_id` a few lines below), still fully removable by
// the user from the search bar like any other default filter.
//
// No finer hook exists to add just this one context key: the dialog's
// context dict is built entirely inline inside reconcileOnReconcileLine(),
// so this overrides the whole method - kept otherwise identical to the
// native implementation (see button_list.js). Re-sync this if Odoo changes
// that method upstream.
patch(BankRecButtonList.prototype, {
    reconcileOnReconcileLine() {
        const context = {
            kanban_view_ref: "account_accountant.view_account_move_line_kanban_bank_rec_widget",
            list_view_ref: "account_accountant.view_account_move_line_list_bank_rec_widget",
            search_view_ref: "account_accountant.view_account_move_line_search_bank_rec_widget",
            preferred_aml_value: -this.props.suspenseAccountLine.amount_currency,
            preferred_aml_currency_id: this.props.suspenseAccountLine.currency_id.id,
            ...(this.statementLineData.partner_id
                ? { search_default_partner_id: this.statementLineData.partner_id.id }
                : {}),
            ...(this.statementLineData.journal_id
                ? { search_default_journal_id: this.statementLineData.journal_id.id }
                : {}),
        };

        this.addDialog(
            BankRecSelectCreateDialog,
            {
                title: _t("Search: Journal Items to Match"),
                noCreate: true,
                domain: this.getReconcileButtonDomain(),
                resModel: "account.move.line",
                size: "xl",
                context: context,
                onSelected: async (moveLines) => {
                    await this.orm.call(
                        "account.bank.statement.line",
                        "set_line_bank_statement_line",
                        [this.statementLineData.id, moveLines]
                    );
                    await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
                        this.env.model.root.records
                    );
                    this.props.statementLine.load();
                    this.bankReconciliation.reloadChatter();
                    this.restoreFocus();
                },
                suspenseAccountLine: this.props.suspenseAccountLine,
                reference: this.statementLineData.payment_ref,
                date: this.statementLineData.date,
            },
            {
                onClose: () => {
                    this.restoreFocus();
                },
            }
        );
    },
});
