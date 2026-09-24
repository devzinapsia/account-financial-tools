from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """A standard module upgrade only overwrites an already-translated
    string when Odoo is started with --overwrite-existing-translations,
    which most deploy pipelines (including odoo.sh's automatic rebuild on
    push) don't pass. That meant a msgid that got a translation once - even
    an empty/wrong one, from an earlier, not-yet-fully-translated pass of
    this module's own i18n files - never picked up later corrections no
    matter how many times the .po files themselves were fixed and the
    module version bumped. Force a real overwrite once here so this stops
    depending on how the deploy pipeline happens to invoke -u.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env['ir.module.module'].search([
        ('name', '=', 'account_statement_reconcile_improvements'),
    ])
    module._update_translations(overwrite=True)
