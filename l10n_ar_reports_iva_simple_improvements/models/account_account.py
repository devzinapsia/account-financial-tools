from odoo import _, api, models
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    def _l10n_ar_reports_iva_simple_improvements_concept_tag_ids(self):
        """ The 4 account tags used by l10n_ar_reports_simple(_improvements) to determine
        the ARCA "Concepto" (Bien / Locación / Servicio / Bien de Uso) of purchase report lines. """
        return self.env['account.account.tag'].browse([
            self.env.ref('l10n_ar_reports_simple.tag_leases_rentals_account').id,
            self.env.ref('l10n_ar_reports_simple.tag_fixed_asset_account').id,
            self.env.ref('l10n_ar_reports_iva_simple_improvements.tag_goods_account').id,
            self.env.ref('l10n_ar_reports_iva_simple_improvements.tag_services_account').id,
        ])

    @api.constrains('tag_ids')
    def _check_l10n_ar_reports_iva_simple_improvements_single_concept_tag(self):
        concept_tags = self._l10n_ar_reports_iva_simple_improvements_concept_tag_ids()
        for account in self:
            assigned_tags = account.tag_ids & concept_tags
            if len(assigned_tags) > 1:
                raise ValidationError(_(
                    "Account %(account)s has more than one ARCA IVA Simple concept tag assigned (%(tags)s)."
                    " Only one of Locaciones / Bienes de Uso / Bienes / Servicios can be set on the same account.",
                    account=account.display_name,
                    tags=", ".join(assigned_tags.mapped('name')),
                ))
