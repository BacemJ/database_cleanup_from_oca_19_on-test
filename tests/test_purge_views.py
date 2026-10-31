# Copyright 2026 Bacem Jarraya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import tagged

from .common import Common, environment


# Use post_install to get all models loaded more info: odoo/odoo#13458
@tagged("post_install", "-at_install")
class TestCleanupPurgeLineView(Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with environment() as env:
            View = env["ir.ui.view"]
            cls.dead_module = env["ir.module.module"].search(
                [("state", "=", "uninstalled")], limit=1
            ).name
            cls.dead_parent = View.create(
                {
                    "name": "database_cleanup_test_parent",
                    "key": "%s.database_cleanup_test_parent" % cls.dead_module,
                    "type": "qweb",
                    "arch": "<t t-name='%s.database_cleanup_test_parent'/>"
                    % cls.dead_module,
                }
            ).id
            cls.dead_child = View.create(
                {
                    "name": "database_cleanup_test_child",
                    "type": "qweb",
                    "inherit_id": cls.dead_parent,
                    "mode": "extension",
                    "arch": "<xpath expr='.' position='inside'/>",
                }
            ).id
            cls.live_view = View.create(
                {
                    "name": "database_cleanup_test_live",
                    "key": "base.database_cleanup_test_live",
                    "type": "qweb",
                    "arch": "<t t-name='base.database_cleanup_test_live'/>",
                }
            ).id

    def test_find_and_purge(self):
        with environment() as env:
            wizard = env["cleanup.purge.wizard.view"].create({})
            found = wizard.purge_line_ids.mapped("view_id").ids
            self.assertIn(self.dead_parent, found)
            self.assertIn(self.dead_child, found)
            self.assertNotIn(self.live_view, found)
            wizard.purge_all()
            View = env["ir.ui.view"].with_context(active_test=False)
            self.assertFalse(View.browse(self.dead_parent).exists())
            self.assertFalse(View.browse(self.dead_child).exists())
            self.assertTrue(View.browse(self.live_view).exists())
            View.browse(self.live_view).unlink()
