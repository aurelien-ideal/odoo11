# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import json


class StockMoveLine(models.Model):
    _name= 'stock.move.line'
    _inherit = ['stock.move.line', 'barcodes.barcode_events_mixin']

    product_barcode = fields.Char(related='product_id.barcode')
    location_processed = fields.Boolean()

    def on_barcode_scanned(self, barcode):
        context=dict(self.env.context)
        # As there is no quantity, just add the quantity
        if context.get('only_create') and context.get('serial'):
            if barcode in [x.lot_name for x in self.pack_lot_ids]:
                return { 'warning': {
                            'title': _('You have entered this serial number already'),
                            'message': _('You have already scanned the serial number "%(barcode)s"') % {'barcode': barcode},
                        }}
            else:
                self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_name': barcode})
        elif context.get('only_create') and not context.get('serial'):
            corresponding_pl = self.pack_lot_ids.filtered(lambda r: r.lot_name == barcode)
            if corresponding_pl:
                corresponding_pl[0].qty = corresponding_pl[0].qty + 1.0
            else:
                self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_name': barcode})
        elif not context.get('only_create'):
            corresponding_pl = self.pack_lot_ids.filtered(lambda r: r.lot_id.name == barcode)
            if corresponding_pl:
                if context.get('serial') and corresponding_pl[0].qty == 1.0:
                    return {'warning': {'title': _('You have entered this serial number already'),
                            'message': _('You have already scanned the serial number "%(barcode)s"') % {'barcode': barcode},}}
                else:
                    corresponding_pl[0].qty = corresponding_pl[0].qty + 1.0
                    corresponding_pl[0].plus_visible = (corresponding_pl[0].qty_todo == 0.0) or (corresponding_pl[0].qty < corresponding_pl[0].qty_todo)
            else:
                # Search lot with correct name
                lots = self.env['stock.production.lot'].search([('product_id', '=', self.product_id.id), ('name', '=', barcode)])
                if lots:
                    self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_id': lots[0].id, 'plus_visible': False})
                else:
                    # If operation type allows for creating
                    if context.get('create_lots'):
                        lot_id = self.env['stock.production.lot'].with_context({'mail_create_nosubscribe': True}).create({'name': barcode, 'product_id': self.product_id.id})
                        self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_id': lot_id.id, 'plus_visible': not context.get('serial')})
                    else:
                        return { 'warning': {
                            'title': _('No lot found'),
                            'message': _('There is no production lot for "%(product)s" corresponding to "%(barcode)s"') % {'product': self.product_id.name, 'barcode': barcode},
                        }}


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'barcodes.barcode_events_mixin']

    @api.multi
    def get_po_to_split_from_barcode(self, barcode):
        ''' Returns the 'Split lot' action for the PO matching the barcode '''
        product_id = self.env['product.product'].search([('barcode', '=', barcode)])
        candidates = self.env['stock.move.line'].search([
            ('picking_id', 'in', self.ids),
            ('product_barcode', '=', barcode),
            ('location_processed', '=', False),
            ('result_package_id', '=', False),
        ])

        action_ctx = dict(self.env.context,
            default_picking_id=self.id,
            serial=self.product_id.tracking == 'serial',
            default_product_id=product_id.id,
            candidates=candidates.ids)
        view_id = self.env.ref('stock_barcode.view_barcode_lot_form').id
        return {
            'name': _('Lot/Serial Number Details'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock_barcode.lot',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'target': 'new',
            'context': action_ctx}

    def new_product_scanned(self, barcode):
        product_id = self.env['product.product'].search([('barcode', '=', barcode)])
        if not product_id or product_id.tracking == 'none':
            return self.on_barcode_scanned(barcode)
        else:
            return self.get_po_to_split_from_barcode(barcode)

    def _check_product(self, product, qty=1.0):
        corresponding_po = self.move_line_ids.filtered(lambda r: r.product_id.id == product.id and not r.result_package_id and not r.location_processed)
        if corresponding_po:
            corresponding_po = corresponding_po[0]
            if not corresponding_po.lots_visible:#product.tracking=='none':
                new_po = False
                last_po = False
                for po in corresponding_po:
                    last_po = po
                    if po.product_uom_qty > po.qty_done:
                        new_po = po
                        break
                corresponding_po = new_po or last_po
                corresponding_po.qty_done += qty
        else:
            picking_type_lots = (self.picking_type_id.use_create_lots or self.picking_type_id.use_existing_lots)
            self.move_line_ids += self.move_line_ids.new({
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'qty_done': (product.tracking == 'none' and picking_type_lots) and qty or 0.0,
                'product_uom_qty': 0.0,
                # TDE FIXME: those fields are compute without inverse: unnecessary ?
                'from_loc': self.location_id.name,
                'to_loc': self.location_dest_id.name,
                'fresh_record': False,
                'state':'assigned',
                'lots_visible': product.tracking != 'none' and picking_type_lots,
            })
        return True

    def _check_source_package(self, package):
        corresponding_po = self.move_line_ids.filtered(lambda r: r.package_id.id == package.id and r.result_package_id.id == package.id)
        for po in corresponding_po:
            po.qty_done = po.product_uom_qty
        return corresponding_po and True or False

    def _check_destination_package(self, package):
        #put in pack logic
        corresponding_po = self.move_line_ids.filtered(lambda r: not r.result_package_id and r.qty_done > 0)
        for packop in corresponding_po:
            qty_done = packop.qty_done
            if qty_done < packop.product_uom_qty:
                if not packop.pack_lot_ids:
                    packop.product_uom_qty = packop.product_uom_qty - qty_done
                    packop.qty_done = 0.0
                    self.move_line_ids += self.move_line_ids.new({
                        'product_id': packop.product_id.id,
                        'package_id': packop.package_id.id,
                        'product_uom_id': packop.product_uom_id.id,
                        'location_id': packop.location_id.id,
                        'location_dest_id': packop.location_dest_id.id,
                        'qty_done': qty_done,
                        'product_uom_qty': qty_done,
                        # TDE FIXME: those fields are compute without inverse: unnecessary ?
                        'from_loc': packop.location_id.name + (packop.package_id and (' : ' + packop.package_id.name) or ''),
                        'to_loc': packop.location_dest_id.name + ' : ' + package.name,
                        'result_package_id': package.id,
                        'lots_visible': packop.product_id.tracking != 'none',
                    })
                else:
                    self.move_line_ids += self.move_line_ids.new({
                        'product_id': packop.product_id.id,
                        'package_id': packop.package_id.id,
                        'product_uom_id': packop.product_uom_id.id,
                        'location_id': packop.location_id.id,
                        'location_dest_id': packop.location_dest_id.id,
                        'qty_done': 0.0,
                        'product_uom_qty': packop.product_uom_qty - qty_done,
                        # TDE FIXME: those fields are compute without inverse: unnecessary ?
                        'from_loc': packop.from_loc,
                        'to_loc': packop.to_loc,
                        'lots_visible': packop.product_id.tracking != 'none',
                    })
                    packop.result_package_id = package.id
                    packop.to_loc = packop.location_dest_id.name + ' : ' + package.name
                    packop.product_uom_qty = qty_done
            else:
                packop.result_package_id = package
                packop.to_loc = packop.location_dest_id.name + ' : ' + package.name
        corresponding_pack_po = self.move_line_ids.filtered(lambda r: not r.result_package_id and r.qty_done > 0)
        for packop in corresponding_pack_po:
            packop.to_loc = packop.location_dest_id.name + ' : ' + package.name
            packop.result_package_id = package.id
        return True

    def _check_destination_location(self, location):
        corresponding_po = self.move_line_ids.filtered(lambda r: not r.location_processed and r.qty_done > 0)
        for packop in corresponding_po:
            qty_done = packop.qty_done
            if qty_done < packop.product_uom_qty:
                if not packop.pack_lot_ids:
                    packop.product_uom_qty = packop.product_uom_qty - qty_done
                    packop.qty_done = 0.0
                    self.move_line_ids += self.move_line_ids.new({
                        'package_id': packop.package_id.id,
                        'product_id': packop.product_id.id,
                        'product_uom_id': packop.product_uom_id.id,
                        'location_id': packop.location_id.id,
                        'location_dest_id': location.id,
                        'qty_done': qty_done,
                        'product_uom_qty': qty_done,
                        # TDE FIXME: those fields are compute without inverse: unnecessary ?
                        'from_loc': packop.location_id.name + (packop.package_id and (' : ' + packop.package_id.name) or ''),
                        'to_loc': location.name + (packop.result_package_id and (' : '  + packop.result_package_id.name) or ''),
                        'location_processed': True,
                        'result_package_id': packop.result_package_id.id,
                        'lots_visible': packop.product_id.tracking != 'none',
                    })
                else:
                    self.move_line_ids += self.move_line_ids.new({
                        'product_id': packop.product_id.id,
                        'package_id': packop.package_id.id,
                        'product_uom_id': packop.product_uom_id.id,
                        'location_id': packop.location_id.id,
                        'location_dest_id': packop.location_dest_id.id,
                        'qty_done': 0.0,
                        'product_uom_qty': packop.product_uom_qty - qty_done,
                        # TDE FIXME: those fields are compute without inverse: unnecessary ?
                        'from_loc': packop.from_loc,
                        'to_loc': packop.to_loc,
                        'lots_visible': packop.product_id.tracking != 'none',
                    })
                    packop.location_processed = True
                    packop.location_dest_id = location.id
                    packop.to_loc = packop.location_dest_id.name + (packop.result_package_id and (' : '  + packop.result_package_id.name) or '')
                    packop.product_uom_qty = qty_done
            else:
                packop.location_dest_id = location.id
                packop.to_loc = packop.location_dest_id.name + (packop.result_package_id and (' : '  + packop.result_package_id.name) or '')
                packop.location_processed = True
        corresponding_pack_po = self.move_line_ids.filtered(lambda r: not r.location_processed and r.qty_done > 0)
        for packop in corresponding_pack_po:
            packop.location_dest_id = location.id
            packop.to_loc = packop.location_dest_id.name + (packop.result_package_id and (' : '  + packop.result_package_id.name) or '')
            packop.location_processed = True
        return True

    def on_barcode_scanned(self, barcode):
        if not self.picking_type_id.barcode_nomenclature_id:
            # Logic for products
            product = self.env['product.product'].search(['|', ('barcode', '=', barcode), ('default_code', '=', barcode)], limit=1)
            if product:
                if self._check_product(product):
                    return

            product_packaging = self.env['product.packaging'].search([('barcode', '=', barcode)], limit=1)
            if product_packaging.product_id:
                if self._check_product(product_packaging.product_id,product_packaging.qty):
                    return

            # Logic for packages in source location
            if self.move_line_ids:
                package_source = self.env['stock.quant.package'].search([('name', '=', barcode), ('location_id', 'child_of', self.location_id.id)], limit=1)
                if package_source:
                    if self._check_source_package(package_source):
                        return

            # Logic for packages in destination location
            package = self.env['stock.quant.package'].search([('name', '=', barcode), '|', ('location_id', '=', False), ('location_id','child_of', self.location_dest_id.id)], limit=1)
            if package:
                if self._check_destination_package(package):
                    return

            # Logic only for destination location
            location = self.env['stock.location'].search(['|', ('name', '=', barcode), ('barcode', '=', barcode)], limit=1)
            if location and location.parent_left < self.location_dest_id.parent_right and location.parent_left >= self.location_dest_id.parent_left:
                if self._check_destination_location(location):
                    return
        else:
            parsed_result = self.picking_type_id.barcode_nomenclature_id.parse_barcode(barcode)
            if parsed_result['type'] in ['weight', 'product']:
                if parsed_result['type'] == 'weight':
                    product_barcode = parsed_result['base_code']
                    qty = parsed_result['value']
                else: #product
                    product_barcode = parsed_result['code']
                    qty = 1.0
                product = self.env['product.product'].search(['|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)], limit=1)
                if product:
                    if self._check_product(product, qty):
                        return

            if parsed_result['type'] == 'package':
                if self.move_line_ids:
                    package_source = self.env['stock.quant.package'].search([('name', '=', parsed_result['code']), ('location_id', 'child_of', self.location_id.id)], limit=1)
                    if package_source:
                        if self._check_source_package(package_source):
                            return
                package = self.env['stock.quant.package'].search([('name', '=', parsed_result['code']), '|', ('location_id', '=', False), ('location_id','child_of', self.location_dest_id.id)], limit=1)
                if package:
                    if self._check_destination_package(package):
                        return

            if parsed_result['type'] == 'location':
                location = self.env['stock.location'].search(['|', ('name', '=', parsed_result['code']), ('barcode', '=', parsed_result['code'])], limit=1)
                if location and location.parent_left < self.location_dest_id.parent_right and location.parent_left >= self.location_dest_id.parent_left:
                    if self._check_destination_location(location):
                        return

            product_packaging = self.env['product.packaging'].search([('barcode', '=', product_barcode)], limit=1)
            if product_packaging.product_id:
                if self._check_product(product_packaging.product_id,product_packaging.qty):
                    return

        return {'warning': {
            'title': _('Wrong barcode'),
            'message': _('The barcode "%(barcode)s" doesn\'t correspond to a proper product, package or location.') % {'barcode': barcode}
        }}


class StockPickingType(models.Model):

    _inherit = 'stock.picking.type'

    @api.multi
    def get_action_picking_tree_ready_kanban(self):
        return self._get_action('stock_barcode.stock_picking_action_kanban')
