import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

TRUE_LEAF = (1, "=", 1)


def _strip_state_leaves(domain):
    """Replace every condition on the bill's Status by an always-true leaf:
    up to 19.0.1.x, authorization happened before confirming, so policies
    were scoped to draft bills (the default domain did so); from 19.0.2.0.0
    on they are evaluated while the bill is being confirmed, where a
    condition on the Status can no longer be relied on.
    """
    changed = False
    result = []
    for item in domain:
        if isinstance(item, (list, tuple)) and len(item) == 3 and item[0] == "state":
            result.append(TRUE_LEAF)
            changed = True
        else:
            result.append(item)
    return result, changed


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    policies = env["account.vendor.bill.authorization.policy"].with_context(active_test=False).search([])
    for policy in policies:
        domain = safe_eval(policy.domain or "[]")
        new_domain, changed = _strip_state_leaves(domain)
        if changed:
            policy.domain = str(new_domain)
            _logger.info("Policy %s: removed its Status conditions", policy.display_name)

    # Authorization now happens once the bill is confirmed: drafts still
    # awaiting (or refused) an authorization under the old flow are
    # evaluated again when they are confirmed. Drafts already authorized
    # keep their authorization.
    drafts = env["account.move"].search(
        [
            ("move_type", "in", ["in_invoice", "in_refund"]),
            ("state", "=", "draft"),
            ("authorization_state", "in", ["to_authorize", "rejected"]),
        ]
    )
    drafts.write({"authorization_state": "not_required", "authorized_by_id": False})
    _logger.info("Reset the authorization status of %s draft vendor bills", len(drafts))

    removed = env["account.move"]._cleanup_stale_authorization_requests()
    _logger.info("Removed %s stale vendor bill authorization request activities", removed)
