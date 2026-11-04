import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

/**
 * AutoComplete keeping the caret where the user clicks: the standard one
 * selects the whole text on focus, which is unhandy to edit a list of
 * addresses.
 */
class CopiesAutoComplete extends AutoComplete {
    onInputFocus(ev) {
        this.props.onFocus(ev);
    }
}

/** Split ``value`` into the addresses already typed and the last one. */
function splitLastAddress(value) {
    const index = Math.max(value.lastIndexOf(","), value.lastIndexOf(";"));
    return [value.slice(0, index + 1), value.slice(index + 1).trim()];
}

/**
 * Free-text list of email addresses (Cc / Bcc) where typing "@" followed by
 * some letters lists the matching internal users, like the mentions of the
 * chatter; picking one replaces the mention with the user's email.
 */
export class TransactionCopiesInput extends Component {
    static template = "mail_transaction_cc.TransactionCopiesInput";
    static components = { AutoComplete: CopiesAutoComplete };
    static props = {
        value: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        title: { type: String, optional: true },
        class: { type: String, optional: true },
        onInput: { type: Function, optional: true },
        onCommit: { type: Function },
    };
    static defaultProps = { value: "", placeholder: "", title: "", class: "", onInput: () => {} };

    setup() {
        this.orm = useService("orm");
    }

    get sources() {
        return [{ options: (request) => this.loadOptions(request) }];
    }

    async loadOptions(request) {
        const [, last] = splitLastAddress(request || "");
        if (!last.startsWith("@") || last.slice(1).includes("@")) {
            return [];
        }
        const users = await this.orm.call("mail.transaction.cc.rule", "search_copy_users", [
            last.slice(1),
        ]);
        return users.map((user) => ({
            label: `${user.name} <${user.email}>`,
            onSelect: () => this.selectUser(request, user),
        }));
    }

    selectUser(request, user) {
        const [head] = splitLastAddress(request);
        const typed = head.replace(/[,;]\s*$/, "").trim();
        this.props.onCommit(typed ? `${typed}, ${user.email}` : user.email);
    }
}

/** Form field widget for the Cc / Bcc of the sending wizards. */
export class TransactionCopiesField extends Component {
    static template = "mail_transaction_cc.TransactionCopiesField";
    static components = { TransactionCopiesInput };
    static props = { ...standardFieldProps, placeholder: { type: String, optional: true } };

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    commit(value) {
        if (value !== this.value) {
            this.props.record.update({ [this.props.name]: value || false });
        }
    }
}

registry.category("fields").add("transaction_cc_emails", {
    component: TransactionCopiesField,
    supportedTypes: ["char"],
    extractProps: ({ placeholder }) => ({ placeholder }),
});
