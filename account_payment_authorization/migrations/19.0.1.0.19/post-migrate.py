import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Up to 19.0.1.0.18, "authorization requested" activities were only
    # closed on an explicit decision, so payments that stopped needing
    # authorization (edit, cancel, confirmation...) kept them open, and
    # every repeated confirm attempt scheduled them again.
    env = api.Environment(cr, SUPERUSER_ID, {})
    removed = env["account.payment"]._cleanup_stale_authorization_requests()
    _logger.info("Removed %s stale payment authorization request activities", removed)
