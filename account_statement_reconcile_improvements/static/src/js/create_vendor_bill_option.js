import { patch } from "@web/core/utils/patch";
import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";

// 3.11 - "Create bill" entry in the "..." dropdown, right below "Upload
// Bills" - see static/src/xml/create_vendor_bill_option.xml for the item
// itself, and models/account_bank_statement_line.py's
// action_create_vendor_bill() for why account_accountant's own "Upload
// Bills" can't be reused here (it always requires an attachment).
patch(BankRecButtonList.prototype, {
    async createVendorBill() {
        const action = await this.orm.call("account.bank.statement.line", "action_create_vendor_bill", [
            this.statementLineData.id,
        ]);
        this.restoreFocus();
        return this.action.doAction(action);
    },
});
