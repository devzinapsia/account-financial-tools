import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { BankRecKanbanControlPanel } from "@account_accountant/components/bank_reconciliation/control_action/control_action";

patch(BankRecKanbanControlPanel.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
    },

    async actionAutoReconcileUnassigned() {
        const lineIds = this.env.model.root.records
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
        this.env.model.load();
    },
});
