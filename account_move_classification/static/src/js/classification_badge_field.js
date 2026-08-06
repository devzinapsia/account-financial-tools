/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { TagsList } from "@web/core/tags_list/tags_list";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { Domain } from "@web/core/domain";
import { getFieldDomain } from "@web/model/relational_model/utils";
import {
    extractM2OFieldProps,
    m2oSupportedOptions,
    m2oSupportedTypes,
} from "@web/views/fields/many2one/many2one_field";

export class ClassificationBadgeField extends Component {
    static template = "account_move_classification.ClassificationBadgeField";
    static components = { TagsList, Many2XAutocomplete };
    static props = {
        ...standardFieldProps,
        canCreate: { type: Boolean, optional: true },
        canCreateEdit: { type: Boolean, optional: true },
        canOpen: { type: Boolean, optional: true },
        canQuickCreate: { type: Boolean, optional: true },
        canScanBarcode: { type: Boolean, optional: true },
        canWrite: { type: Boolean, optional: true },
        context: { type: Object, optional: true },
        decorations: { type: Object, optional: true },
        domain: { type: [Array, Function], optional: true },
        nameCreateField: { type: String, optional: true },
        openActionContext: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        searchLimit: { type: Number, optional: true },
        searchThreshold: { type: Number, optional: true },
        string: { type: String, optional: true },
    };

    setup() {
        // Tracks the color after an in-memory selection so the chip updates
        // immediately without waiting for the non-stored related field to reload.
        this.state = useState({ color: null });
    }

    get relation() {
        return this.props.record.fields[this.props.name].relation;
    }

    get hasValue() {
        return !!this.props.record.data[this.props.name];
    }

    get displayName() {
        const value = this.props.record.data[this.props.name];
        if (!value) return "";
        // Server loads as [id, display_name]; after record.update() it can be
        // an object {id, display_name} — handle both.
        if (Array.isArray(value)) return value[1] || "";
        return value.display_name || "";
    }

    get colorIndex() {
        // Prefer the locally tracked color (set after a client-side selection)
        // so the chip updates immediately without saving.
        if (this.state.color !== null) return this.state.color;
        return this.props.record.data["classification_color"] ?? 0;
    }

    get activeActions() {
        return {
            create: this.props.canCreate ?? true,
            createEdit: this.props.canCreateEdit ?? true,
            write: this.props.canWrite ?? true,
        };
    }

    // Ask Many2XAutocomplete to also fetch the color field so we can update
    // the chip color immediately without a round-trip after save.
    get specification() {
        return { color: {} };
    }

    get tags() {
        if (!this.hasValue) return [];
        return [
            {
                id: "classification_tag",
                text: this.displayName,
                colorIndex: this.colorIndex,
                onDelete: () => this.clearValue(),
            },
        ];
    }

    getDomain = () => {
        return Domain.and([
            getFieldDomain(this.props.record, this.props.name, this.props.domain),
        ]).toList(this.props.context || {});
    };

    update = async (records) => {
        const record = records && records[0];
        if (record) {
            // Cache the color locally so the chip updates before next save.
            this.state.color = record.color ?? 0;
            const display_name = record.display_name || record.name || "";
            await this.props.record.update({
                [this.props.name]: { id: record.id, display_name },
            });
        }
    };

    clearValue = async () => {
        this.state.color = null;
        await this.props.record.update({ [this.props.name]: false });
    };
}

registry.category("fields").add("classification_badge", {
    component: ClassificationBadgeField,
    displayName: "Classification Badge",
    extractProps: extractM2OFieldProps,
    supportedOptions: m2oSupportedOptions,
    supportedTypes: m2oSupportedTypes,
});
