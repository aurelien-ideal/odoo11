# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import unittest
from odoo.tests.common import TransactionCase


class TestDeliveryUSPS(TransactionCase):

    def setUp(self):
        super(TestDeliveryUSPS, self).setUp()

        self.iPadMini = self.env.ref('product.product_product_6')

        # Add a full address to "Your Company"
        self.your_company = self.env.ref('base.main_partner')
        self.your_company.write({'country_id': self.env.ref('base.us').id,
                                 'state_id': self.env.ref('base.state_us_5').id,
                                 'city': 'San Francisco',
                                 'street': '51 Federal Street',
                                 'zip': '94107',
                                 'phone': 9874582356})
        self.agrolait = self.env.ref('base.res_partner_2')
        self.think_big_system = self.env.ref('base.res_partner_18')
        self.think_big_system.write({'phone': 3132223456,
                                     'street': '1 Infinite Loop',
                                     'street2': 'Tower 2',
                                     'city': 'Cupertino',
                                     'state_id': self.env.ref('base.state_us_13').id,
                                     'country_id': self.env.ref('base.us').id,
                                     'zip': '95014-2083'})
        # additional test address for Canada
        self.quebec = self.env.ref('base.state_ca_qc')
        self.montreal = self.env['res.partner'].create({'name': 'Vieux-Port de Montreal',
                                                        'street': '333 Rue de la Commune O',
                                                        'city': 'Montreal',
                                                        'zip': 'H2Y2E2',
                                                        'state_id': self.quebec.id,
                                                        'country_id': self.env.ref('base.ca').id})

    @unittest.skip("USPS test disabled: We do not want to overload USPS with runbot's requests")
    def test_01_usps_basic_us_domestic_flow(self):
        SaleOrder = self.env['sale.order']

        sol_vals = {'product_id': self.iPadMini.id,
                    'name': "[A1232] iPad Mini",
                    'product_uom': self.env.ref('product.product_uom_unit').id,
                    'product_uom_qty': 1.0,
                    'price_unit': self.iPadMini.lst_price}

        so_vals = {'partner_id': self.think_big_system.id,
                   'carrier_id': self.env.ref('delivery_usps.delivery_carrier_usps_domestic').id,
                   'order_line': [(0, None, sol_vals)]}

        sale_order = SaleOrder.create(so_vals)
        sale_order.get_delivery_price()
        self.assertTrue(sale_order.delivery_rating_success, "USPS has not been able to rate this order (%s)" % sale_order.delivery_message)
        self.assertGreater(sale_order.delivery_price, 0.0, "USPS delivery cost for this SO has not been correctly estimated.")
        sale_order.set_delivery_line()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.force_assign()
        picking.move_lines[0].quantity_done = 1.0
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        picking.action_done()
        picking.send_to_shipper()
        self.assertIsNot(picking.carrier_tracking_ref, False, "USPS did not return any tracking number")
        self.assertGreater(picking.carrier_price, 0.0, "USPS carrying price is probably incorrect")

        picking.cancel_shipment()

        self.assertFalse(picking.carrier_tracking_ref, "Carrier Tracking code has not been properly deleted")
        self.assertEquals(picking.carrier_price, 0.0, "Carrier price has not been properly deleted")

    @unittest.skip("USPS test disabled: We do not want to overload USPS with runbot's requests")
    def test_02_usps_basic_international_flow(self):
        SaleOrder = self.env['sale.order']

        sol_vals = {'product_id': self.iPadMini.id,
                    'name': "[A1232] iPad Mini",
                    'product_uom': self.env.ref('product.product_uom_unit').id,
                    'product_uom_qty': 1.0,
                    'price_unit': self.iPadMini.lst_price}

        so_vals = {'partner_id': self.agrolait.id,
                   'carrier_id': self.env.ref('delivery_usps.delivery_carrier_usps_international').id,
                   'order_line': [(0, None, sol_vals)]}

        sale_order = SaleOrder.create(so_vals)
        sale_order.get_delivery_price()
        self.assertTrue(sale_order.delivery_rating_success, "USPS has not been able to rate this order (%s)" % sale_order.delivery_message)
        self.assertGreater(sale_order.delivery_price, 0.0, "USPS delivery cost for this SO has not been correctly estimated.")
        sale_order.set_delivery_line()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.force_assign()
        picking.move_lines[0].quantity_done = 1.0
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        picking.action_done()
        picking.send_to_shipper()
        self.assertIsNot(picking.carrier_tracking_ref, False, "USPS did not return any tracking number")
        self.assertGreater(picking.carrier_price, 0.0, "USPS carrying price is probably incorrect")

        picking.cancel_shipment()
        self.assertFalse(picking.carrier_tracking_ref, "Carrier Tracking code has not been properly deleted")
        self.assertEquals(picking.carrier_price, 0.0, "Carrier price has not been properly deleted")

    @unittest.skip("USPS test disabled: We do not want to overload USPS with runbot's requests")
    def test_03_usps_ship_to_canada_flow(self):
        SaleOrder = self.env['sale.order']

        sol_vals = {'product_id': self.iPadMini.id,
                    'name': "[A1232] iPad Mini",
                    'product_uom': self.env.ref('product.product_uom_unit').id,
                    'product_uom_qty': 1.0,
                    'price_unit': self.iPadMini.lst_price}

        so_vals = {'partner_id': self.montreal.id,
                   'carrier_id': self.env.ref('delivery_usps.delivery_carrier_usps_international').id,
                   'order_line': [(0, None, sol_vals)]}

        sale_order = SaleOrder.create(so_vals)
        sale_order.get_delivery_price()
        self.assertTrue(sale_order.delivery_rating_success, "USPS has not been able to rate this order (%s)" % sale_order.delivery_message)
        self.assertGreater(sale_order.delivery_price, 0.0, "USPS delivery cost for this SO has not been correctly estimated.")
        sale_order.set_delivery_line()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sale Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.force_assign()
        picking.move_lines[0].quantity_done = 1.0
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        picking.action_done()
        picking.send_to_shipper()
        self.assertIsNot(picking.carrier_tracking_ref, False, "USPS did not return any tracking number")
        self.assertGreater(picking.carrier_price, 0.0, "USPS carrying price is probably incorrect")

        picking.cancel_shipment()
        self.assertFalse(picking.carrier_tracking_ref, "Carrier Tracking code has not been properly deleted")
        self.assertEquals(picking.carrier_price, 0.0, "Carrier price has not been properly deleted")
