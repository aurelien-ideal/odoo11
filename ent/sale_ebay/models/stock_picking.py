# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.one
    def do_transfer(self):
        result = super(StockPicking, self).do_transfer()
        self._ebay_update_carrier(transfered=True)
        return result

    @api.one
    def _ebay_update_carrier(self, transfered=False):
        so = self.env['sale.order'].search([('name', '=', self.origin), ('origin', 'like', 'eBay')])
        if so.product_id.product_tmpl_id.ebay_use:
            call_data = {
                'OrderLineItemID': so.client_order_ref,
            }
            if transfered:
                call_data['Shipped'] = True
            if self.carrier_tracking_ref and self.carrier_id:
                call_data['Shipment'] = {
                    'ShipmentTrackingDetails': {
                        'ShipmentTrackingNumber': self.carrier_tracking_ref,
                        'ShippingCarrierUsed': self.carrier_id.name,
                    },
                }
            self.env['product.template'].ebay_execute("CompleteSale", call_data)
