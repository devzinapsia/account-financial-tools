from odoo import fields, models

PAY_NOW_JOURNAL_TYPES = ("bank", "cash", "credit")


class ResCompany(models.Model):
    _inherit = "res.company"

    bypass_journal_ids = fields.Many2many(
        "account.journal",
        relation="res_company_vendor_bill_bypass_journal_rel",
        column1="company_id",
        column2="journal_id",
        string="Journals that bypass authorization",
        domain=[("type", "in", PAY_NOW_JOURNAL_TYPES)],
        help="Only journals that can be chosen as the pay now journal of a "
        "vendor bill. A vendor bill paid on confirmation with one of them "
        "does not require authorization, unless an 'Always block' policy "
        "matches it. Leave empty to keep the pay now journal working as "
        "before, with no bypass.",
    )
    bypass_user_ids = fields.Many2many(
        "res.users",
        relation="res_company_vendor_bill_bypass_user_rel",
        column1="company_id",
        column2="user_id",
        string="Users allowed to use this bypass",
        domain=[("share", "=", False)],
        help="Only these users can set a pay now journal on a vendor bill, "
        "or confirm a vendor bill that has one, while journals that bypass "
        "authorization are configured.",
    )
