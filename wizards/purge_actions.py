# Copyright 2026 Bacem Jarraya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
# pylint: disable=consider-merging-classes-inherited
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

LIVE_STATES = ("installed", "to upgrade", "to remove", "to install")
# order matters for purging: crons reference server actions
ACTION_MODELS = (
    "ir.cron",
    "ir.actions.server",
    "ir.actions.act_window",
    "ir.actions.report",
    "ir.actions.client",
    "ir.actions.act_url",
)


class CleanupPurgeWizardAction(models.TransientModel):
    _inherit = "cleanup.purge.wizard"
    _name = "cleanup.purge.wizard.action"
    _description = "Purge actions and crons of uninstalled modules"

    @api.model
    def _action_target_model(self, record):
        """Name of the model an action works on, or False if it has none."""
        if record._name == "ir.actions.act_window":
            return record.res_model
        if record._name == "ir.actions.report":
            return record.model
        if record._name in ("ir.actions.server", "ir.cron"):
            return record.model_id.model if record.model_id else False
        return False

    @api.model
    def find(self):
        """Actions and scheduled actions that are left behind:
        * all their XML ids belong to modules that are not installed, or
        * they have no XML id and the model they work on no longer exists.
        """
        cr = self.env.cr
        cr.execute("SELECT name, state FROM ir_module_module")
        live = {name for name, state in cr.fetchall() if state in LIVE_STATES}
        res = []
        for model_name in ACTION_MODELS:
            if model_name not in self.env:
                continue
            cr.execute(
                "SELECT res_id, module FROM ir_model_data WHERE model = %s",
                (model_name,),
            )
            xmods = {}
            for res_id, module in cr.fetchall():
                xmods.setdefault(res_id, set()).add(module)
            records = self.env[model_name].with_context(active_test=False).search([])
            if model_name == "ir.actions.server":
                # server actions of a cron are handled with their cron
                crons = self.env["ir.cron"].with_context(active_test=False).search([])
                records -= crons.ir_actions_server_id
            for record in records:
                modules = xmods.get(record.id, set())
                if modules:
                    if modules & live:
                        continue
                    reason = self.env._(
                        "XML id of uninstalled module: %s", ", ".join(sorted(modules))
                    )
                else:
                    target = self._action_target_model(record)
                    if not target or target in self.env:
                        continue
                    reason = self.env._("no XML id, model does not exist: %s", target)
                res.append(
                    Command.create(
                        {
                            "name": "%s: %s" % (model_name, record.display_name),
                            "res_model": model_name,
                            "res_id": record.id,
                            "reason": reason,
                        }
                    )
                )
        if not res:
            raise UserError(self.env._("No leftover actions found"))
        return res

    purge_line_ids = fields.One2many(
        "cleanup.purge.line.action", "wizard_id", "Actions to purge"
    )
