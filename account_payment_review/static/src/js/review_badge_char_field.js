import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";

// Badge colors per review status. "Not required" (and no status at all)
// shows no badge, so the list only highlights payments a reviewer cares
// about, the same way core's "To review" badge on journal entries does.
const REVIEW_BADGE_CLASSES = {
    pending: "text-bg-info",
    reviewed: "text-bg-success",
    observed: "text-bg-danger",
    answered: "text-bg-warning",
};

/**
 * Char field (the payment number) followed by a review status badge,
 * modeled on account's char_with_placeholder_field_to_check. Needs the
 * review_state field loaded in the same view.
 */
export class ReviewBadgeCharField extends CharField {
    static template = "account_payment_review.ReviewBadgeCharField";

    get reviewState() {
        return this.props.record.data.review_state;
    }

    get reviewBadgeClass() {
        return REVIEW_BADGE_CLASSES[this.reviewState] || "";
    }

    get reviewBadgeLabel() {
        const selection = this.props.record.fields.review_state?.selection || [];
        const option = selection.find(([value]) => value === this.reviewState);
        return option ? option[1] : "";
    }
}

export const reviewBadgeCharField = {
    ...charField,
    component: ReviewBadgeCharField,
};

registry.category("fields").add("review_badge_char", reviewBadgeCharField);
