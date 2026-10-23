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
        return self._build_cuit_to_partner_map().get(cuit, self.browse())

    @api.model
    def _build_cuit_to_partner_map(self):
        """Same matching rule as _find_unique_partner_by_cuit(), but
        resolves every CUIT found among contacts with a VAT set from a
        single query, instead of one query (and one full re-scan of every
        such contact) per CUIT looked up.

        A bank statement import calls this kind of lookup once per row -
        thousands of times for a large file. _find_unique_partner_by_cuit()
        alone turned that into thousands of repeats of the exact same
        ``search([('vat', '!=', False)])`` (plus the Python-side filtering
        over every one of those partners, since CUIT formatting varies
        enough - dashes, leading zeros - that it can't be matched directly
        in SQL, so the query itself can't be narrowed to one specific CUIT
        either), making total import time grow with
        rows × contacts-with-a-vat instead of just rows. Callers that
        resolve many CUITs in the same pass (wizard/base_import_import.py)
        should call this once per batch and look up each row's CUIT in the
        returned dict, instead of calling _find_unique_partner_by_cuit()
        per row.

        :return: dict of normalized CUIT -> single-record (never empty)
            res.partner recordset, one entry per CUIT that resolved to a
            partner. A CUIT with no match at all has no entry (use
            ``.get(cuit, self.browse())``, same as
            _find_unique_partner_by_cuit() itself returns).
        """
        # A client's own company CUIT routinely shows up in a bank
        # statement's free-text legend - most commonly on a transfer
        # between the client's own bank accounts, where the bank's export
        # often names the account holder (the client itself) rather than
        # a real counterpart. Matching that CUIT would assign the
        # company's own res.partner as the line's contact - never a
        # correct result (an AR/AP document is never issued to oneself),
        # and actively harmful: every feature that filters by contact
        # (the reconciliation search dialog's own partner pre-filter, the
        # probable-duplicate check) would then search using that wrong
        # partner, while the transfer's real counterpart journal item
        # typically has no partner_id at all - hiding the correct match
        # instead of narrowing down to it. Checked across every company in
        # the database, not just the one being imported for: a group's
        # own inter-company transfers can carry any of its other
        # companies' CUITs just as easily.
        own_company_partner_ids = set(self.env['res.company'].sudo().search([]).partner_id.ids)
        candidates = self.search([('vat', '!=', False), ('id', 'not in', list(own_company_partner_ids))])
        by_cuit = {}
        for partner in candidates:
            cuit = normalize_vat(partner.vat)
            if not cuit:
                continue
            by_cuit[cuit] = by_cuit.get(cuit, self.browse()) | partner
        result = {}
        for cuit, matches in by_cuit.items():
            parents = matches.filtered(lambda partner: not partner.parent_id)
            pool = parents or matches
            result[cuit] = pool if len(pool) == 1 else pool.sorted(
                key=lambda partner: (partner.create_date, partner.id)
            )[0]
        return result
