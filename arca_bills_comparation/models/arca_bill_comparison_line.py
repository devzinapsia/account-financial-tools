from odoo import fields, models


class ArcaBillComparisonLine(models.Model):
    _name = "arca.bill.comparison.line"
    _description = "ARCA Bill Comparison Result Line"
    _order = "arca_point_of_sale, arca_number_from"

    batch_id = fields.Many2one(
        "arca.bill.comparison.batch",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="batch_id.company_id", store=True)
    move_id = fields.Many2one("account.move", string="Vendor bill", ondelete="set null")

    result = fields.Selection(
        [
            ("match", "Match"),
            ("difference", "Difference"),
            ("pending_in_odoo", "Pending in Odoo"),
            ("pending_in_arca", "Pending in ARCA"),
        ],
        required=True,
        index=True,
    )
    difference_detail = fields.Text(string="Difference detail")

    # Fields below mirror, in order, the 30 columns of ARCA's "Mis Comprobantes
    # Recibidos" export. For "Pending in ARCA" lines (a vendor bill with no
    # matching ARCA row) they are populated from the Odoo bill itself instead,
    # so the grid still shows comparable data.
    arca_date = fields.Date(string="Date")
    arca_voucher_type_raw = fields.Char(string="Voucher type")
    arca_voucher_type_code = fields.Char(string="Voucher type code")
    arca_point_of_sale = fields.Integer(string="Point of sale")
    arca_number_from = fields.Integer(string="Number from")
    arca_number_to = fields.Integer(string="Number to")
    arca_authorization_code = fields.Char(string="Authorization code")
    arca_issuer_id_type = fields.Char(string="Issuer ID type")
    arca_issuer_vat = fields.Char(string="Issuer VAT")
    arca_issuer_name = fields.Char(string="Issuer name")
    arca_recipient_id_type = fields.Char(string="Recipient ID type")
    arca_recipient_vat = fields.Char(string="Recipient VAT")
    arca_exchange_rate = fields.Float(string="Exchange rate", digits=(16, 4))
    arca_currency_raw = fields.Char(string="Currency")
    arca_untaxed_vat_0 = fields.Monetary(string="Untaxed base VAT 0%", currency_field="arca_currency_id")
    arca_vat_2_5 = fields.Monetary(string="VAT 2.5%", currency_field="arca_currency_id")
    arca_untaxed_vat_2_5 = fields.Monetary(string="Untaxed base VAT 2.5%", currency_field="arca_currency_id")
    arca_vat_5 = fields.Monetary(string="VAT 5%", currency_field="arca_currency_id")
    arca_untaxed_vat_5 = fields.Monetary(string="Untaxed base VAT 5%", currency_field="arca_currency_id")
    arca_vat_10_5 = fields.Monetary(string="VAT 10.5%", currency_field="arca_currency_id")
    arca_untaxed_vat_10_5 = fields.Monetary(string="Untaxed base VAT 10.5%", currency_field="arca_currency_id")
    arca_vat_21 = fields.Monetary(string="VAT 21%", currency_field="arca_currency_id")
    arca_untaxed_vat_21 = fields.Monetary(string="Untaxed base VAT 21%", currency_field="arca_currency_id")
    arca_vat_27 = fields.Monetary(string="VAT 27%", currency_field="arca_currency_id")
    arca_untaxed_vat_27 = fields.Monetary(string="Untaxed base VAT 27%", currency_field="arca_currency_id")
    arca_untaxed_total = fields.Monetary(string="Total taxed base", currency_field="arca_currency_id")
    arca_non_taxed_amount = fields.Monetary(string="Non taxed amount", currency_field="arca_currency_id")
    arca_exempt_operations = fields.Monetary(string="Exempt operations", currency_field="arca_currency_id")
    arca_other_taxes = fields.Monetary(string="Other taxes", currency_field="arca_currency_id")
    arca_total_vat = fields.Monetary(string="Total VAT", currency_field="arca_currency_id")
    arca_total_amount = fields.Monetary(string="Total amount", currency_field="arca_currency_id")

    # Only used so Monetary fields render with the right symbol; the actual
    # ARCA-vs-Odoo currency comparison is a soft-field check done in
    # arca.bill.comparison.batch, not through this field. Set explicitly at
    # line creation time (see ArcaBillComparisonBatch), not computed here.
    arca_currency_id = fields.Many2one("res.currency", string="Currency (for amount display)")
