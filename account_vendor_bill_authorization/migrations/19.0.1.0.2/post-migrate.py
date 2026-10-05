import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Up to 19.0.1.0.1, "authorization requested" activities were only
    # closed on an explicit decision, so bills that stopped needing
    # authorization (bypass, edit, posting, cancel...) kept them open, and
    # every repeated confirm attempt scheduled them again.
    env = api.Environment(cr, SUPERUSER_ID, {})
    removed = env["account.move"]._cleanup_stale_authorization_requests()
    _logger.info("Removed %s stale vendor bill authorization request activities", removed)
