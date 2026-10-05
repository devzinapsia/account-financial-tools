from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class InflationAdjustment(models.TransientModel):
    _inherit = "inflation.adjustment"

    specify_individual_entries = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Specify individual entries?",
        default="yes",
        help="If you answer no, all the entries posted in the selected journal"
        " will be excluded from the inflation adjustment.",
    )
    exclusion_journal_id = fields.Many2one(
        "account.journal",
        string="Journal where they are posted",
        domain=[("type", "=", "general")],
        check_company=True,
    )

    def _excludes_whole_journal(self):
        self.ensure_one()
        return self.open_cloure_entry == "yes" and self.specify_individual_entries == "no"

    def _get_hidden_fields_values(self):
        """Return the values that reset the closing/opening fields hidden by
        the current answers, so they can't leak into the move line domain."""
        self.ensure_one()
        vals = {}
        if self.open_cloure_entry != "yes" or self.specify_individual_entries != "yes":
            if self.closure_move_id:
                vals["closure_move_id"] = False
            if self.open_move_id:
                vals["open_move_id"] = False
        if not self._excludes_whole_journal() and self.exclusion_journal_id:
            vals["exclusion_journal_id"] = False
        return vals

    @api.onchange("open_cloure_entry", "specify_individual_entries")
    def _onchange_closing_opening_answers(self):
        for wizard in self:
            wizard.update(wizard._get_hidden_fields_values())

    @api.constrains("open_cloure_entry", "specify_individual_entries", "exclusion_journal_id", "journal_id")
    def _check_exclusion_journal(self):
        for wizard in self.filtered(lambda w: w._excludes_whole_journal()):
            if not wizard.exclusion_journal_id:
                raise ValidationError(
                    _("Please select the journal where the closing/opening entries are posted.")
                )
            if wizard.exclusion_journal_id == wizard.journal_id:
                raise ValidationError(
                    _(
                        "The journal where the closing/opening entries are posted can't be the same"
                        " journal where the inflation adjustment entry is created, otherwise previous"
                        " inflation adjustment entries would also be excluded."
                    )
                )

    def get_move_line_domain(self):
        res = super().get_move_line_domain()
        if self._excludes_whole_journal() and self.exclusion_journal_id:
            res += [("journal_id", "!=", self.exclusion_journal_id.id)]
        return res

    def confirm(self):
        self.ensure_one()
        vals = self._get_hidden_fields_values()
        if vals:
            # Same cleanup as the onchange, for wizards not filled in through the form
            self.write(vals)
        return super().confirm()
