# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"
    _name = "sale.order"

    def _get_payment_type(self):
        if any(line.product_id.recurring_invoice for line in self.sudo().order_line):
            return 'form_save'
        return super(SaleOrder, self)._get_payment_type()


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = "sale.order.line"

    recurring_product = fields.Boolean('Recurring Product', related="product_id.recurring_invoice")
