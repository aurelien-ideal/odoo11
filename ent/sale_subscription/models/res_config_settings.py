# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_sale_subscription_dashboard = fields.Boolean('Sale Subscription Dashboard')
    module_sale_subscription_asset = fields.Boolean('Deferred revenue management for subscriptions')
