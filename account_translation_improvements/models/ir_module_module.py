from odoo import api, models

from ..hooks import OVERRIDDEN_NAMES, force_translations


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def _account_translation_improvements_force_translations(self):
        """Called from data/account_overrides.xml, see force_translations()."""
        force_translations(self.env, "account_translation_improvements", OVERRIDDEN_NAMES)
