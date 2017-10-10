# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    min_days_between_followup = fields.Integer(related='company_id.min_days_between_followup', string='Minimum days between two follow-ups')

    @api.multi
    def open_followup_level_form(self):
        followup = self.env['account_followup.followup'].search([], limit=1)
        return {
                 'type': 'ir.actions.act_window',
                 'name': 'Payment Follow-ups',
                 'res_model': 'account_followup.followup',
                 'res_id': followup.id or False,
                 'view_mode': 'form,tree',
         }
