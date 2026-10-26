from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The "Purchase" transaction type was renamed to "Request for quotation /
    purchase order". A standard upgrade keeps the existing Spanish
    translation ("Compra") of the old name, so force this module's
    translations to be reloaded from its .po files once."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.module.module"].search([("name", "=", "mail_transaction_cc")])._update_translations(overwrite=True)
