# -*- coding: utf-8 -*-
from odoo import api, models
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def action_confirm(self):
        return super(SaleOrder, self.with_context(default_allow_forecast=True)).action_confirm()
