# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import json

class stockInventoryLine(models.Model):
    _inherit = "stock.inventory.line"
    product_barcode = fields.Char(related='product_id.barcode')

class StockInventory(models.Model):
    _name = 'stock.inventory'
    _inherit = ['stock.inventory', 'barcodes.barcode_events_mixin']

    scan_location_id = fields.Many2one('stock.location', 'Scanned Location', store=False)

    @api.model
    def open_new_inventory(self):
        action = self.env.ref('stock_barcode.stock_inventory_action_new_inventory').read()[0]
        if self.env.ref('stock.warehouse0', raise_if_not_found=False):
            new_inv = self.env['stock.inventory'].create({
                'filter': 'partial',
                'name': fields.Date.context_today(self),
            })
            new_inv.action_start()
            action['res_id'] = new_inv.id
        return action

    def _add_product(self, product, qty=1.0):
        corresponding_line = self.line_ids.filtered(lambda r: r.product_id.id == product.id and (self.scan_location_id.id == r.location_id.id or not self.scan_location_id))
        if corresponding_line:
            corresponding_line[0].product_qty += qty
        else:
            StockQuant = self.env['stock.quant']
            company_id = self.company_id.id
            if not company_id:
                company_id = self._uid.company_id.id
            dom = [('company_id', '=', company_id), ('location_id', '=', self.scan_location_id.id or self.location_id.id), ('lot_id', '=', False),
                        ('product_id','=', product.id), ('owner_id', '=', False), ('package_id', '=', False)]
            quants = StockQuant.search(dom)
            th_qty = sum([x.quantity for x in quants])
            self.line_ids += self.line_ids.new({
                'location_id': self.scan_location_id.id or self.location_id.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'theoretical_qty': th_qty,
                'product_qty': qty,
            })
        return True

    def on_barcode_scanned(self, barcode):
        product = self.env['product.product'].search([('barcode', '=', barcode)])
        if product:
            self._add_product(product)
            return

        product_packaging = self.env['product.packaging'].search([('barcode', '=', barcode)])
        if product_packaging.product_id:
            self._add_product(product_packaging.product_id, product_packaging.qty)
            return

        location = self.env['stock.location'].search([('barcode', '=', barcode)])
        if location:
            self.scan_location_id = location[0]
            return
