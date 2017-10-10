# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- coding: utf-8 -*-

import unittest
import odoo.tests


@odoo.tests.common.at_install(False)
@odoo.tests.common.post_install(True)
class TestUi(odoo.tests.HttpCase):

    # As the tour creates models and fields, which updates the registry,
    # using a test cursor like the resy of HTTPCase won't work
    registry_test_mode = False

    @unittest.skip('pending fix for multi-cursor lock problem')
    def test_new_app(self):
        self.phantom_js("/web?studio=app_creator",
                        "odoo.__DEBUG__.services['web_tour.tour'].run('web_studio_new_app_tour')",
                        "odoo.__DEBUG__.services['web_tour.tour'].tours.web_studio_new_app_tour.ready",
                        login="admin")
