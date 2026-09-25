from odoo import api, models

from odoo.addons.account_translation_improvements.hooks import force_translations

from ..hooks import OVERRIDDEN_NAMES


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def _account_translation_improvements_account_batch_payment_force_translations(self):
        """Called from data/account_batch_payment_overrides.xml, see
        account_translation_improvements' force_translations()."""
        force_translations(
            self.env, "account_translation_improvements_account_batch_payment", OVERRIDDEN_NAMES
        )
