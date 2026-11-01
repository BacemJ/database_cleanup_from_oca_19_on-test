# Copyright 2026 Bacem Jarraya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
# pylint: disable=consider-merging-classes-inherited
from psycopg2 import IntegrityError

from odoo import fields, models
from odoo.exceptions import UserError, ValidationError


class CleanupPurgeLineView(models.TransientModel):
    _inherit = "cleanup.purge.line"
    _name = "cleanup.purge.line.view"
    _description = "Cleanup Purge Line View"

    wizard_id = fields.Many2one(
        "cleanup.purge.wizard.view", "Purge Wizard", readonly=True
    )
    view_id = fields.Many2one("ir.ui.view", "View", ondelete="set null")
    reason = fields.Char(readonly=True)

    def purge(self):
        """Unlink views upon manual confirmation, children before parents."""
        if self:
            objs = self
        else:
            objs = self.env["cleanup.purge.line.view"].browse(
                self.env.context.get("active_ids")
            )
        to_unlink = objs.filtered(lambda x: not x.purged and x.view_id)
        self.logger.info("Purging views: %s", to_unlink.mapped("name"))

        def depth(view):
            level = 0
            while view.inherit_id:
                view = view.inherit_id
                level += 1
            return level

        done = self.browse()
        for line in sorted(
            to_unlink, key=lambda x: depth(x.view_id.with_context(active_test=False)),
            reverse=True,
        ):
            view = line.view_id.with_context(active_test=False)
            try:
                with self.env.cr.savepoint():
                    view.exists().unlink()
            except (IntegrityError, ValidationError, UserError) as exc:
                self.logger.warning("Cannot purge view %s: %s", line.name, exc)
                line.reason = self.env._("NOT PURGED: %s", str(exc).strip()[:200])
                continue
            done |= line
        return done.write({"purged": True})
