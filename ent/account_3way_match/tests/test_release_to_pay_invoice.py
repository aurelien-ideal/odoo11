# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.addons.account.tests.account_test_classes import AccountingTestCase


import logging
_logger = logging.getLogger(__name__)

class TestReleaseToPayInvoice(AccountingTestCase):

    def setUp(self):
        super(TestReleaseToPayInvoice, self).setUp()
        self.PurchaseOrder = self.env['purchase.order']
        self.PurchaseOrderLine = self.env['purchase.order.line']
        self.AccountInvoice = self.env['account.invoice']
        self.AccountInvoiceLine = self.env['account.invoice.line']
        self.StockBackorderConfirmation = self.env['stock.backorder.confirmation']
        self.StockPicking = self.env['stock.picking']

    def test_00_release_to_pay_invoice_flow(self):
        self.partner_id = self.env.ref('base.res_partner_1')
        self.product_id_1 = self.env.ref('account_3way_match.demo_product')

        # Let's create a new Purchase Order ...
        self.purchase_order = self.PurchaseOrder.create({
            'partner_id': self.partner_id.id,
            'order_line': [
                (0, 0, {
                    'name': self.product_id_1.name,
                    'product_id': self.product_id_1.id,
                    'product_qty': 10.0,
                    'product_uom': self.product_id_1.uom_po_id.id,
                    'price_unit': 500.0,
                    'date_planned': fields.Datetime.now(),
                })]
        })

        # ... confirm it ...
        self.purchase_order.button_confirm()

        # ... and create a new invoice corresponding to it.
        self.invoice_1 = self.AccountInvoice.create({
            'partner_id': self.partner_id.id,
            'purchase_id': self.purchase_order.id,
            'account_id': self.partner_id.property_account_payable_id.id,
            'type': 'in_invoice'
        })

        self.invoice_1.purchase_order_change()
        for line in self.invoice_1.invoice_line_ids:
            self.assertEquals(line.quantity, 0, "Vendor Bill: newly created bill's lines should have a null quantity.")

            # invoice_1 should contain only one line, for product_id_1
            self.assertEquals(line.product_id, self.product_id_1, "Vendor Bill: newly created bill contains some line for another product.")

            # We update the ordered quantity of product_id_1 on invoice_2 (the previous assert assures we're on the right product)
            line.write({'quantity': 3.0})

        self.invoice_1.action_invoice_open()

        # Nothing has been received yet, but the invoice has been done. Its status must be 'no'.
        self.assertEqual(self.invoice_1.release_to_pay, 'no', 'Vendor Bill: Vendor bill_status should be "No"')

        # We now receive 2 of the products we ordered...
        self.picking_1 = self.purchase_order.picking_ids[0]
        self.picking_1.force_assign()
        self.picking_1.move_line_ids.write({'qty_done': 2.0})
        self.picking_1.button_validate()

        # ... and create a back order.
        self.stock_backorder_confirmation_1 = self.StockBackorderConfirmation.create({
            'pick_ids': [(4, self.picking_1.id)]
            })
        self.stock_backorder_confirmation_1.process()

        # Only part of what was billed got delivered, the invoice should be in exception state
        self.assertEqual(self.invoice_1.release_to_pay, 'exception', 'Vendor Bill: Vendor bill_status should be "Exception"')

        # Now, we create a second invoice for the same order (it will have a total of 0).
        self.invoice_2 = self.AccountInvoice.create({
            'partner_id': self.partner_id.id,
            'purchase_id': self.purchase_order.id,
            'account_id': self.partner_id.property_account_payable_id.id,
            'type': 'in_invoice'
        })
        self.invoice_2.purchase_order_change()

        for line in self.invoice_2.invoice_line_ids:
            self.assertEquals(line.quantity, 0, "Vendor Bill: newly created bill's lines should have a null quantity.")

            # invoice_2 should contain only one line, for product_id_1
            self.assertEquals(line.product_id, self.product_id_1, "Vendor Bill: newly created bill contains some line for another product.")

            # We update the ordered quantity of product_id_1 on invoice_2 (the previous assert assures we're on the right product)
            line.write({'quantity': 7.0})

        # invoice_2 should be in exception state, since received and billed quantities still differ
        self.assertEqual(self.invoice_2.release_to_pay, 'exception', 'Vendor Bill: Vendor bill_status should be "Exception"')

        # Finally, we receive the last 8 products ...
        self.picking_2 = self.StockPicking.search([('backorder_id', '=', self.picking_1.id)])
        self.picking_2.force_assign()
        self.picking_2.move_line_ids.write({'qty_done': 8.0})
        self.picking_2.button_validate()

        # We received everything, in the same amount as on the bills, so both their status should be 'yes'
        self.assertEqual(self.invoice_1.release_to_pay, 'yes', 'Vendor Bill: Vendor bill_status should be "Yes"')
        self.assertEqual(self.invoice_2.release_to_pay, 'yes', 'Vendor Bill: Vendor bill_status should be "Yes"')
