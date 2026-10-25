import logging

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class MailTransactionCcType(models.Model):
    _name = "mail.transaction.cc.type"
    _description = "Transaction type for email copies"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    # Plain Char (not a Many2one to ir.model) so types can be declared for
    # models of modules that are not installed yet (e.g. purchase.order).
    model_name = fields.Char(string="Model", required=True)
    base_domain = fields.Char(
        string="Base domain",
        default="[]",
        help="Fixed filter that defines which records belong to this type.",
    )
    responsible_field = fields.Char(
        string="Responsible field",
        help="Technical name of the Many2one field to res.users used as the "
        "record's responsible.",
    )
    available = fields.Boolean(
        compute="_compute_available",
        search="_search_available",
        help="The model of this type is installed.",
    )

    _code_uniq = models.Constraint("UNIQUE(code)", "The code must be unique.")

    @api.depends("model_name")
    def _compute_available(self):
        for cc_type in self:
            cc_type.available = cc_type.model_name in self.env

    def _search_available(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return NotImplemented
        installed = [name for name in self.sudo().search([]).mapped("model_name") if name in self.env]
        positive = (operator == "=") == value
        return [("model_name", "in" if positive else "not in", installed)]

    def _filter_records(self, records):
        """Return the subset of ``records`` matching this type's fixed filter
        and the model-specific exclusions."""
        self.ensure_one()
        if not records or records._name != self.model_name:
            return records.browse()
        try:
            domain = safe_eval(self.base_domain or "[]")
        except Exception:
            _logger.exception("Invalid base domain on email copy type %s", self.code)
            return records.browse()
        return records.filtered_domain(domain)._mail_transaction_cc_filter_records()

    def _get_responsible_user(self, record):
        self.ensure_one()
        field = record._fields.get(self.responsible_field or "")
        if not field or field.type != "many2one" or field.comodel_name != "res.users":
            return self.env["res.users"]
        return record[self.responsible_field]
