from odoo import api, models

from ..tools.ar_id_extraction import normalize_vat


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _find_unique_partner_by_cuit(self, cuit):
        """Resolve a CUIT (11 digits, no separators) to a single partner.

        Odoo commonly copies a company's VAT onto its own child contacts
        (branches, contact persons), so a plain ``vat`` search can return
        several records for the same CUIT. Zinapsia's matching rule:

        1. Discard contacts with a parent_id set (keep only top-level ones).
        2. If more than one top-level partner still shares the CUIT, keep
           the oldest one (lowest create_date, id as tie-break).

        Returns a single-record (possibly empty) res.partner recordset -
        never raises, and never guesses among multiple companies beyond
        this deterministic tie-break.
        """
        if not cuit:
            return self.browse()
        candidates = self.search([('vat', '!=', False)])
        matches = candidates.filtered(lambda partner: normalize_vat(partner.vat) == cuit)
        if not matches:
            return self.browse()
        parents = matches.filtered(lambda partner: not partner.parent_id)
        pool = parents or matches
        if len(pool) == 1:
            return pool
        return pool.sorted(key=lambda partner: (partner.create_date, partner.id))[0]
