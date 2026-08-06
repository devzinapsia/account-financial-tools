from odoo import SUPERUSER_ID


def post_init_hook(env):
    _reload_translations(env)


def _reload_translations(env):
    module = env["ir.module.module"].search([("name", "=", "account_move_classification")])
    if not module:
        return
    langs = env["res.lang"].search([("active", "=", True), ("code", "!=", "en_US")])
    for lang in langs:
        module._update_translations(lang.code)
