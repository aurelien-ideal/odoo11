# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields

from odoo.addons.timesheet_grid_sale.models.sale import DEFAULT_INVOICED_TIMESHEET


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    invoiced_timesheet = fields.Selection([
        ('all', "All recorded timesheets"),
        ('approved', "Approved timesheets only"),
    ], default='all', string="Timesheets Invoicing")

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('sale.invoiced_timesheet', self.invoiced_timesheet)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            invoiced_timesheet=params.get_param('sale.invoiced_timesheet', DEFAULT_INVOICED_TIMESHEET)
        )
        return res
