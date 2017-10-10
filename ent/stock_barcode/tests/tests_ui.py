# -*- coding: utf-8 -*-

import odoo.tests

@odoo.tests.common.at_install(False)
@odoo.tests.common.post_install(True)
class TestUi(odoo.tests.HttpCase):

    def setUp(self):
        super(TestUi, self).setUp()
        # To test all scanning features, enable lots tracking, packages and multi location
        self.env["stock.config.settings"].create({
            "group_stock_production_lot": 1,
            "group_stock_tracking_lot": 1,
            "group_stock_multi_locations": 1,
            "group_stock_multi_warehouses": 1,
        }).execute()
        self.env['product.product'].search([("barcode", "=", "420196872340")]).write({
            "tracking": "lot"
        })

    def launch_tour(self, tour_id, login="admin"):
        url_path = "/web#action=stock_barcode_main_menu"
        exec_code = "odoo.__DEBUG__.services['web.Tour'].run('" + tour_id + "', 'test')"
        wait_ready = "odoo.__DEBUG__.services['web.Tour'].tours." + tour_id
        self.phantom_js(url_path, exec_code, wait_ready, login)

    def test_inventory(self):
        self.launch_tour("stock_barcode_inventory")

    def test_out_picking(self):
        self.launch_tour("stock_barcode_out_picking")

    def test_in_picking(self):
        self.launch_tour("stock_barcode_in_picking")
