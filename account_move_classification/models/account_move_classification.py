from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMoveClassification(models.Model):
    _name = "account.move.classification"
    _description = "Invoice Classification"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    color = fields.Integer(default=0)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        help="Leave empty to make this classification available in all companies.",
    )

    @api.constrains("name", "company_id")
    def _check_unique_name(self):
        for rec in self:
            domain = [("name", "=", rec.name), ("id", "!=", rec.id)]
            if rec.company_id:
                domain += [("company_id", "=", rec.company_id.id)]
            else:
                domain += [("company_id", "=", False)]
            if self.search_count(domain):
                raise ValidationError(
                    _("Classification name '%s' must be unique per company.", rec.name)
                )

    def name_get(self):
        result = []
        for rec in self:
            name = rec.code and f"[{rec.code}] {rec.name}" or rec.name
            result.append((rec.id, name))
        return result
