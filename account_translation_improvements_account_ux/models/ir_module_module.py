from odoo import api, models

from ..hooks import set_collect_context_key


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def _account_translation_improvements_account_ux_set_context(self):
        """Called from data/account_ux_overrides.xml, see
        set_collect_context_key()."""
        set_collect_context_key(self.env, True)
