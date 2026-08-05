/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import {
    Many2OneField,
    extractM2OFieldProps,
    m2oSupportedOptions,
    m2oSupportedTypes,
} from "@web/views/fields/many2one/many2one_field";

/**
 * ClassificationBadgeField
 *
 * Renders account.move.classification as a colored chip in readonly mode
 * and falls back to the standard Many2One input in edit mode.
 * Reads the color index from the sibling field `classification_color` on
 * the same record (declared invisible="1" in the view).
 */
export class ClassificationBadgeField extends Component {
    static template = "account_move_classification.ClassificationBadgeField";
    static components = { Many2OneField };
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
}

registry.category("fields").add("classification_badge", {
    component: ClassificationBadgeField,
    displayName: "Classification Badge",
    extractProps: extractM2OFieldProps,
    supportedOptions: m2oSupportedOptions,
    supportedTypes: m2oSupportedTypes,
});
