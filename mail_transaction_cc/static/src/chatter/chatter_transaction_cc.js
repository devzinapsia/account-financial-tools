import { Chatter } from "@mail/chatter/web_portal/chatter";
import { Thread } from "@mail/core/common/thread_model";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

/**
 * Cc / Bcc typed in the chatter's "Send message" box, by "model,id" of the
 * thread. Read when the message is posted, then dropped so the next message
 * starts again from the email copy rules.
 */
const copiesByThread = new Map();

function threadKey(thread) {
    return `${thread.model},${thread.id}`;
}

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        this.transactionCcOrm = useService("orm");
        this.transactionCc = useState({ available: false, cc: "", bcc: "" });
    },

    toggleComposer(mode = false, options = {}) {
        const result = super.toggleComposer(...arguments);
        if (mode === "message") {
            this.loadTransactionCc();
        }
        return result;
    },

    async loadTransactionCc() {
        const thread = this.state.thread;
        Object.assign(this.transactionCc, { available: false, cc: "", bcc: "" });
        if (!thread?.id || !thread.model || thread.model === "discuss.channel") {
            return;
        }
        const copies = await this.transactionCcOrm.call(
            "mail.transaction.cc.rule",
            "get_chatter_copies",
            [thread.model, thread.id]
        );
        if (this.state.thread !== thread) {
            return;
        }
        Object.assign(this.transactionCc, copies);
        if (copies.available) {
            copiesByThread.set(threadKey(thread), this.transactionCc);
        } else {
            copiesByThread.delete(threadKey(thread));
        }
    },
});

patch(Thread.prototype, {
    async post(body, postData = {}, extraData = {}) {
        const key = threadKey(this);
        const copies = copiesByThread.get(key);
        if (copies?.available && !postData.isNote) {
            copiesByThread.delete(key);
            extraData = {
                ...extraData,
                context: {
                    ...(extraData.context || {}),
                    mail_transaction_cc_override: {
                        [key]: { cc: copies.cc || "", bcc: copies.bcc || "" },
                    },
                },
            };
        }
        return super.post(body, postData, extraData);
    },
});
