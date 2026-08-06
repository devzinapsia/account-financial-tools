from odoo.addons.account_move_classification.hooks import _reload_translations


def migrate(env, version):
    _reload_translations(env)
