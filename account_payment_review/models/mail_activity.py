from odoo import models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def _action_done(self, feedback=False, attachment_ids=None):
        handled = self.browse()
        for activity in self.filtered(lambda a: a.res_model and a.res_id):
            Model = self.env.get(activity.res_model)
            if Model is None or not hasattr(Model, "_review_activity_done"):
                continue
            record = Model.browse(activity.res_id).exists()
            if record and record._review_activity_done(activity, feedback):
                handled |= activity
        # The handled activities were already removed by the review action,
        # which also logged the decision in the chatter.
        return super(MailActivity, self - handled)._action_done(feedback=feedback, attachment_ids=attachment_ids)
