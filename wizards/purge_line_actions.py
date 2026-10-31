# Copyright 2026 Bacem Jarraya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
# pylint: disable=consider-merging-classes-inherited
from odoo import fields, models

from .purge_actions import ACTION_MODELS


class CleanupPurgeLineAction(models.TransientModel):
    _inherit = "cleanup.purge.line"
    _name = "cleanup.purge.line.action"
    _description = "Cleanup Purge Line Action"

    wizard_id = fields.Many2one(
        "cleanup.purge.wizard.action", "Purge Wizard", readonly=True
    )
    res_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    reason = fields.Char(readonly=True)

    def purge(self):
        """Unlink actions upon manual confirmation, crons first."""
        if self:
            objs = self
        else:
            objs = self.env["cleanup.purge.line.action"].browse(
                self.env.context.get("active_ids")
            )
        to_unlink = objs.filtered(lambda x: not x.purged and x.res_model)
        self.logger.info("Purging actions: %s", to_unlink.mapped("name"))
        for model_name in ACTION_MODELS:
            ids = [x.res_id for x in to_unlink if x.res_model == model_name]
            if ids:
                self.env[model_name].with_context(active_test=False).browse(
                    ids
                ).exists().unlink()
        return to_unlink.write({"purged": True})
