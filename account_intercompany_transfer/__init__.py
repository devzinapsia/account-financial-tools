from . import models
from . import wizards
from .models.account_intercompany_transfer import SEQUENCE_CODE


def post_init_hook(env):
    """Create the transfer numbering of every company that already exists."""
    env["res.company"].search([])._create_intercompany_transfer_sequences()


def uninstall_hook(env):
    """The per-company sequences are created in code, without an XML id, so
    the module uninstallation would leave them behind.
    """
    env["ir.sequence"].search([("code", "=", SEQUENCE_CODE)]).unlink()
