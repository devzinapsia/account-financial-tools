from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The help of the Cc / Bcc fields of the sending wizards changed (the
    "@user" mentions). A standard upgrade keeps the existing Spanish
    translation of the old help, so force this module's translations to be
    reloaded from its .po files once."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.module.module"].search([("name", "=", "mail_transaction_cc")])._update_translations(overwrite=True)
