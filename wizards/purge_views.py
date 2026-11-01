# Copyright 2026 Bacem Jarraya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
# pylint: disable=consider-merging-classes-inherited
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import SQL

LIVE_STATES = ("installed", "to upgrade", "to remove", "to install")


class CleanupPurgeWizardView(models.TransientModel):
    _inherit = "cleanup.purge.wizard"
    _name = "cleanup.purge.wizard.view"
    _description = "Purge views of uninstalled modules"

    @api.model
    def _get_dead_views(self):
        """Return ``{view_id: reason}`` for views left behind by modules that
        are not installed (uninstalled, uninstallable or no longer present).

        A view is selected when:
        * all its XML ids belong to modules that are not installed, or
        * it has no XML id and its key starts with such a module name, or
        * it has no XML id and its model no longer exists in the registry, or
        * it inherits (directly or not) from a selected view and has no XML id
          of an installed module.

        Website-specific (COW) views are never selected, and neither is
        any view that has an XML id of an installed module; a selected view
        that has such a view among its descendants is dropped as well,
        because it could not be deleted anyway.
        """
        cr = self.env.cr
        cr.execute("SELECT name, state FROM ir_module_module")
        modules = dict(cr.fetchall())
        live = {name for name, state in modules.items() if state in LIVE_STATES}

        cr.execute(
            """
            SELECT v.id, v.model, v.key, v.inherit_id, d.module
              FROM ir_ui_view v
              LEFT JOIN ir_model_data d
                     ON d.model = 'ir.ui.view' AND d.res_id = v.id
             WHERE v.website_id IS NULL
            """
        )
        views = {}
        for view_id, model, key, parent_id, xml_module in cr.fetchall():
            info = views.setdefault(
                view_id,
                {"model": model, "key": key, "parent": parent_id, "xmods": set()},
            )
            if xml_module:
                info["xmods"].add(xml_module)

        dead = {}
        for view_id, info in views.items():
            if info["xmods"]:
                if not info["xmods"] & live:
                    dead[view_id] = self.env._(
                        "XML id of uninstalled module: %s",
                        ", ".join(sorted(info["xmods"])),
                    )
                continue
            prefix = (info["key"] or "").split(".")[0]
            if prefix in modules and prefix not in live:
                dead[view_id] = self.env._(
                    "no XML id, key of uninstalled module: %s", prefix
                )
            elif info["model"] and info["model"] not in self.env:
                dead[view_id] = self.env._(
                    "no XML id, model does not exist: %s", info["model"]
                )

        # descendants of selected views (children have to go first anyway)
        cr.execute("SELECT id, inherit_id FROM ir_ui_view WHERE inherit_id IS NOT NULL")
        parent_of = dict(cr.fetchall())
        children = {}
        for child_id, parent_id in parent_of.items():
            children.setdefault(parent_id, []).append(child_id)
        protected = set()
        stack = list(dead)
        while stack:
            for child_id in children.get(stack.pop(), []):
                if child_id in dead or child_id in protected:
                    continue
                info = views.get(child_id)
                if info is None or info["xmods"] & live:
                    # website COW view or view of an installed module
                    protected.add(child_id)
                    continue
                dead[child_id] = self.env._("inherits from a view being purged")
                stack.append(child_id)

        # a selected view with a protected descendant cannot be deleted
        for view_id in protected:
            parent_id = parent_of.get(view_id)
            while parent_id:
                dead.pop(parent_id, None)
                parent_id = parent_of.get(parent_id)

        # views still referenced through a restrictive foreign key (for
        # example payment.provider.express_checkout_form_view_id) cannot be
        # deleted either: keep them, and keep their parents as well
        cr.execute(
            """
            SELECT c.conrelid::regclass::text, a.attname
              FROM pg_constraint c
              JOIN pg_attribute a
                ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
             WHERE c.contype = 'f'
               AND c.confrelid = 'ir_ui_view'::regclass
               AND c.confdeltype IN ('a', 'r')
               AND c.conrelid <> 'ir_ui_view'::regclass
            """
        )
        referenced = set()
        for table, column in cr.fetchall():
            if not dead:
                break
            cr.execute(
                SQL(
                    "SELECT DISTINCT %s FROM %s WHERE %s = ANY(%s)",
                    SQL.identifier(column),
                    SQL(table),
                    SQL.identifier(column),
                    list(dead),
                )
            )
            referenced.update(row[0] for row in cr.fetchall())
        for view_id in referenced:
            while view_id:
                dead.pop(view_id, None)
                view_id = parent_of.get(view_id)
        return dead

    @api.model
    def find(self):
        res = []
        dead = self._get_dead_views()
        View = self.env["ir.ui.view"].with_context(active_test=False)
        for view in View.browse(list(dead)).exists():
            res.append(
                Command.create(
                    {
                        "name": "%s [%s]" % (view.key or view.name, view.model or "-"),
                        "view_id": view.id,
                        "reason": dead[view.id],
                    }
                )
            )
        if not res:
            raise UserError(self.env._("No leftover views found"))
        return res

    purge_line_ids = fields.One2many(
        "cleanup.purge.line.view", "wizard_id", "Views to purge"
    )
