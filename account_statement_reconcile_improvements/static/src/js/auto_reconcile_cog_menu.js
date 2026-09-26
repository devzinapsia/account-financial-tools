import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * 'Reconcile by date and amount' cog menu entry.
 *
 * Placed in the bank reconciliation screen's own gear/Actions menu, next to
 * account_online_synchronization's "Find Duplicate Transactions"/"Find
 * Missing Transactions" (same registry, same isDisplayed gate) - a plain
 * <button> in the list/kanban control panel is only ever rendered when
 * something is selected (native Odoo <header> mechanism), which this
 * action can't use since it always applies to every unreconciled,
 * no-partner line of the journal, not a manual selection.
 */
export class AutoReconcileByAmountAndDate extends Component {
    static template = "account_statement_reconcile_improvements.AutoReconcileByAmountAndDate";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    //---------------------------------------------------------------------
    // Protected
    //---------------------------------------------------------------------

    async reconcileByAmountAndDate() {
        const { context } = this.env.searchModel;
        const activeModel = context.active_model;
        let activeIds = [];
        if (activeModel === "account.journal") {
            activeIds = context.active_ids;
        } else if (context.default_journal_id) {
            activeIds = context.default_journal_id;
        }
        await this.action.doActionButton({
            type: "object",
            resModel: "account.journal",
            name: "action_auto_reconcile_by_amount_and_date",
            resIds: activeIds,
        });
        // doActionButton() only auto-refreshes the record/view that owns the
        // widget it was clicked from (a form field, a list row, ...) - a cog
        // menu entry isn't tied to any of those, so without this the
        // reconciled lines only stopped showing as pending after a manual
        // page refresh (F5). soft_reload is the native, documented way to
        // reload the current controller in place, without a full browser
        // reload.
        return this.action.doAction({ type: "ir.actions.client", tag: "soft_reload" });
    }
}

export const autoReconcileByAmountAndDateItem = {
    Component: AutoReconcileByAmountAndDate,
    groupNumber: 5, // same group as fetch missing/find duplicate transactions
    isDisplayed: ({ config, isSmall }) => {
        return (
            !isSmall &&
            config.actionType === "ir.actions.act_window" &&
            ["kanban", "list"].includes(config.viewType) &&
            ["bank_rec_widget_kanban", "bank_rec_list"].includes(config.viewSubType)
        );
    },
};

registry.category("cogMenu").add(
    "auto-reconcile-by-amount-and-date-menu",
    autoReconcileByAmountAndDateItem,
    { sequence: 4 }, // right after "Find Duplicate Transactions" (sequence 3)
);
