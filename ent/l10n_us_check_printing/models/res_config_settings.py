# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    us_check_layout = fields.Selection(related='company_id.us_check_layout', string="Check Layout",
        help="Select the format corresponding to the check paper you will be printing your checks on.\n"
             "In order to disable the printing feature, select 'None'.")
    us_check_multi_stub = fields.Boolean(related='company_id.us_check_multi_stub', string='Multi-Pages Check Stub',
        help="This option allows you to print check details (stub) on multiple pages if they don't fit on a single page.")
    us_check_margin_top = fields.Float(related='company_id.us_check_margin_top', string='Top Margin',
        help="Adjust the margins of generated checks to make it fit your printer's settings.")
    us_check_margin_left = fields.Float(related='company_id.us_check_margin_left', string='Left Margin',
        help="Adjust the margins of generated checks to make it fit your printer's settings.")
