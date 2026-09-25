import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { BankRecKanbanController } from "@account_accountant/components/bank_reconciliation/kanban_controller";

// Patched onto BankRecKanbanController (the widget's Layout-level
// controller), not BankRecKanbanControlPanel: that control panel's whole
// action row - including account_accountant's own Receivable/Payable
// buttons - lives inside <div t-if="selectedStatementLines.length">, and
// the kanban mode of this widget has no checkbox/selection mechanism at
// all, so that row can never actually render there. The chatter toggle
// button (in kanban_controller.xml's "control-panel-navigation-additional"
// slot) is the one part of this widget's control panel confirmed to
// render unconditionally - this button reuses that same slot.
patch(BankRecKanbanController.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");
    },

    async actionAutoReconcileUnassigned() {
        const lineIds = this.model.root.records
            .filter((record) => !record.data.is_reconciled && !record.data.partner_id)
            .map((record) => record.data.id);
        if (!lineIds.length) {
            this.notification.add(_t("No unassigned, unreconciled lines to process."), {
                type: "info",
            });
            return;
        }
        const reconciledCount = await this.orm.call(
            "account.bank.statement.line",
            "action_auto_reconcile_unassigned_by_amount_and_date",
            [lineIds]
        );
        const message = reconciledCount
            ? _t("Line(s) reconciled automatically: ") + reconciledCount
            : _t("No matching open item found for any of those lines.");
        this.notification.add(message, { type: reconciledCount ? "success" : "info" });
        this.model.load();
    },
});
