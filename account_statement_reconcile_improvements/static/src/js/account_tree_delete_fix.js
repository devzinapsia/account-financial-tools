import { patch } from "@web/core/utils/patch";
import { AccountMoveListController } from "@account/views/account_move_list/account_move_list_controller";

// Bug fix (native Odoo, not ours): AccountMoveListController.onDeleteSelectedRecords()
// unconditionally calls account_move_service.getDeletionDialogBody(), which
// calls account.move.check_move_sequence_chain() with the CURRENT list
// view's selected record ids, assuming those ids ARE account.move ids.
//
// This same js_class ("account_tree", registered in
// account_move_list_view.js as accountMoveUploadListView, reusing this exact
// controller) is ALSO used by account.bank.statement's own "Estados de
// cuenta bancarios" list view - for its unrelated upload/attachment
// features - and account.bank.statement is NOT account.move. Deleting a
// bank statement from that list then calls check_move_sequence_chain with
// the STATEMENT's own ids, misread as account.move ids - on a sufficiently
// large/multi-company database, those ids can coincide with a real,
// unrelated account.move record, since account.move and
// account.bank.statement share the same global id sequence (every table's
// id column defaults to the same id_seq sequence) but are entirely
// different tables.
//
// Confirmed against a real case: deleting three statements with ids 6/7/8
// made this check report completely unrelated account.move records 6/8 -
// one nonexistent, one a journal entry in a different company - and the
// delete silently never went through, with no indication the cause had
// nothing to do with the statement being deleted. Odoo's own native code
// never reaches this edge case because account.move's own list/form views
// are the only other callers of onDeleteSelectedRecords on this exact
// controller - this reuse by account.bank.statement, elsewhere in
// account_accountant, is what exposes it.
//
// Guarded here so the sequence-chain check (and its "this operation will
// create a gap" warning, which is meaningless for a model with no sequence
// at all) only ever runs for an actual account.move list - every other
// model reusing this js_class falls back to the same plain
// delete-confirmation the base ListController itself would use.
patch(AccountMoveListController.prototype, {
    async onDeleteSelectedRecords() {
        if (this.model.root.resModel !== "account.move") {
            this.deleteRecordsWithConfirmation(this.deleteConfirmationDialogProps);
            return;
        }
        return super.onDeleteSelectedRecords();
    },
});
