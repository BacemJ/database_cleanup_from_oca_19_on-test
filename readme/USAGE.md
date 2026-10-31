After installation of this module, go to the Settings menu -\> Technical
-\> Database cleanup. This menu is only available to members of the
*Settings* group. Go through the modules, models, columns and
tables entries under this menu (in that order) and find out if there is
orphaned data in your database. You can either delete entries by line,
or sweep all entries in one big step (if you are *really* confident).


To remove leftover views of uninstalled or no longer available modules
(for example Studio), use *Purge views of uninstalled modules*. It lists
views whose XML ids all belong to modules that are not installed, views
without XML id whose key starts with such a module name or whose model no
longer exists, and their inheriting views. Views of installed modules and
website-specific views are never listed. Review the list, then purge by
line or all at once (children are deleted before parents).


Use *Purge actions of uninstalled modules* for leftover crons and
window/server/report/client/URL actions of modules that are not installed,
or that work on a model that no longer exists. Crons are removed before
their server actions. Run it before *Purge obsolete menu entries*, which
then removes the menus left pointing at the deleted actions.

[![Try me on Runbot](https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas)](https://runbot.odoo-community.org/runbot/149/11.0)
