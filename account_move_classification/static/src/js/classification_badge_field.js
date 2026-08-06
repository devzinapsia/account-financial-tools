/** @odoo-module **/

import { Component } from "@odoo/owl";
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

    get relation() {
        return this.props.record.fields[this.props.name].relation;
    }

    get hasValue() {
        return !!this.props.record.data[this.props.name];
    }

    get displayName() {
        const value = this.props.record.data[this.props.name];
        return value ? value[1] : "";
    }

    get colorIndex() {
        return this.props.record.data["classification_color"] ?? 0;
    }

    get activeActions() {
        return {
            create: this.props.canCreate ?? true,
            createEdit: this.props.canCreateEdit ?? true,
            write: this.props.canWrite ?? true,
        };
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
            const name = record.display_name || record.name || "";
            await this.props.record.update({ [this.props.name]: [record.id, name] });
        }
    };

    clearValue = async () => {
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
