# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- coding: utf-8 -*-

import odoo.tests


@odoo.tests.common.at_install(False)
@odoo.tests.common.post_install(True)
class TestUi(odoo.tests.HttpCase):
    def test_ui(self):
        self.phantom_js("/web", "odoo.__DEBUG__.services['web_tour.tour'].run('helpdesk_tour')", ready="odoo.__DEBUG__.services['web_tour.tour'].tours.helpdesk_tour.ready", login="admin")
