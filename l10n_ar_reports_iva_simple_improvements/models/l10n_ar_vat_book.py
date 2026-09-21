from odoo import models
from odoo.tools import SQL


class L10n_ArTaxReportHandler(models.AbstractModel):
    _inherit = 'l10n_ar.tax.report.handler'

    def _vat_simple_build_purchase_query(self, file_type, move_ids):
        """ Full override of l10n_ar_reports_simple's method, to fix the "Concepto" (ARCA
        Concept) determination on purchase report lines.

        Upstream only recognizes 2 of the 4 possible ARCA concepts via account tags
        (Bienes de Uso, Locaciones) and falls back to Concepto 1 (Bien) for any line that
        has neither a product nor one of those 2 tags - which in real data is almost
        always a services expense billed without itemized products (e.g. a services
        invoice with just a description and no product line), so the blind fallback
        silently misclassifies most of those lines as goods instead of services.

        There is no smaller override point upstream for this: the CASE that derives the
        concept is inlined inside one large SQL() built in Python, so this method has to
        duplicate the rest of the query unchanged (moves/taxes selection, aggregation,
        column mapping) and only changes:
        - the tag lookup, extended to the 2 new tags this module adds (Goods, Services),
        - the CASE that derives the concept, with the new priority order (Locaciones >
          Bienes de Uso > Servicios > Bienes > product type - 'combo' products count as
          Bien - > fallback),
        - the ORDER BY used by the DISTINCT ON, extended with the same priority, to keep
          a stable pick if an account improperly carries more than one concept tag (this
          is blocked by a constraint on account.account - see account_account.py - so
          this is only defense in depth, not the primary safeguard),
        - the final ELSE fallback, changed from Concepto 1 (Bien) to Concepto 3
          (Servicio) - the fix for the bug described above.
        """
        columns_map = {"Concepto": 'concept', "Codigo de Alicuota": 'rate_code', "Monto Neto Gravado": 'balance', "Credito Fiscal Facturado": 'vat_amount'}
        if file_type == 'purchase_invoice':
            # Additional column for vendor bills
            columns_map["Credito Fiscal Computable"] = 'vat_amount'

        query = SQL(
            """
                WITH move_lines_with_concept AS (
                    SELECT DISTINCT ON (aml.id)
                        aml.*,
                        CASE
                            WHEN tag_rel.account_account_tag_id = %(lease_tag_id)s THEN 2
                            WHEN tag_rel.account_account_tag_id = %(fixed_tag_id)s THEN 4
                            WHEN tag_rel.account_account_tag_id = %(services_tag_id)s THEN 3
                            WHEN tag_rel.account_account_tag_id = %(goods_tag_id)s THEN 1
                            WHEN pt.type = 'consu' THEN 1
                            WHEN pt.type = 'service' THEN 3
                            WHEN pt.type = 'combo' THEN 1
                            ELSE 3
                        END as concept,
                        btg.l10n_ar_vat_afip_code AS rate_code
                    FROM account_move_line aml
                    LEFT JOIN product_product pp ON aml.product_id = pp.id
                    LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    LEFT JOIN account_account_account_tag tag_rel
                        ON aml.account_id = tag_rel.account_account_id
                        AND tag_rel.account_account_tag_id IN (%(lease_tag_id)s, %(fixed_tag_id)s, %(services_tag_id)s, %(goods_tag_id)s)
                    LEFT JOIN account_move_line_account_tax_rel amltr ON aml.id = amltr.account_move_line_id
                    LEFT JOIN account_tax bt ON amltr.account_tax_id = bt.id
                    LEFT JOIN account_tax_group btg ON bt.tax_group_id = btg.id
                    WHERE
                        aml.move_id IN %(move_ids)s AND
                        btg.l10n_ar_vat_afip_code IN ('3', '4', '5', '6', '8', '9') AND
                        aml.partner_id IS NOT NULL
                    ORDER BY
                        aml.id,
                        -- Prioritize among concept tags in case an account improperly carries more
                        -- than one (blocked by a constraint, see account_account.py), for a stable
                        -- DISTINCT ON selection
                        (CASE
                            WHEN tag_rel.account_account_tag_id = %(lease_tag_id)s THEN 1
                            WHEN tag_rel.account_account_tag_id = %(fixed_tag_id)s THEN 2
                            WHEN tag_rel.account_account_tag_id = %(services_tag_id)s THEN 3
                            WHEN tag_rel.account_account_tag_id = %(goods_tag_id)s THEN 4
                            ELSE 5
                        END)
                )
                SELECT
                    concept,
                    rate_code,
                    SUM(balance) AS balance,
                    ARRAY_AGG(DISTINCT id) as aml_ids,
                    ARRAY_AGG(DISTINCT move_id) as move_ids
                FROM move_lines_with_concept
                GROUP BY concept, rate_code
                ORDER BY concept, rate_code;
            """,
            lease_tag_id=self.env.ref("l10n_ar_reports_simple.tag_leases_rentals_account").id,
            fixed_tag_id=self.env.ref("l10n_ar_reports_simple.tag_fixed_asset_account").id,
            services_tag_id=self.env.ref("l10n_ar_reports_iva_simple_improvements.tag_services_account").id,
            goods_tag_id=self.env.ref("l10n_ar_reports_iva_simple_improvements.tag_goods_account").id,
            move_ids=move_ids,
        )

        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()

        results = []
        for row in data:
            row_data = {}
            for header_name, column in columns_map.items():
                if column == 'vat_amount':
                    value = self._vat_simple_get_taxes_from_row(row)
                else:
                    value = row.get(column, "")
                value = self._vat_simple_transform_column(value)
                row_data[header_name] = value
            results.append(row_data)
        return results
