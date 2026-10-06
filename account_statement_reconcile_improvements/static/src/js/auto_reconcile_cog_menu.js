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
        // page refresh (F5).
        //
        // ir.actions.client/soft_reload (tried first) turned out NOT to fix
        // this reliably: it calls the action service's restore(), which is
        // built for cheap "go back" breadcrumb navigation - it's allowed to
        // reuse the controller's last exported/cached state instead of
        // re-fetching, so the just-reconciled lines kept showing as pending
        // until navigating away to another screen and back (which mounts a
        // fresh controller, forcing a real re-fetch). Calling the view's own
        // model.load() directly - the same call this widget's own
        // kanban_renderer.js already uses after its quick-create flow
        // (validateQuickCreate()) - forces that real re-fetch instead, and
        // also re-triggers the model's onRootLoaded hook (registered by
        // kanban_renderer.js), which recomputes the journal total/reconcile
        // counts alongside the line list.
        return this.env.model.load();
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
