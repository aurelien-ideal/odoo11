# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ticket_count = fields.Integer("Tickets", compute='_compute_ticket_count')

    def _compute_ticket_count(self):
        for partner in self:
            partner.ticket_count = self.env['helpdesk.ticket'].search_count([('partner_id', 'child_of', partner.ids)])

    @api.multi
    def action_open_helpdesk_ticket(self):
        action = self.env.ref('helpdesk.helpdesk_ticket_action_main_tree').read()[0]
        action['context'] = {}
        action['domain'] = [('partner_id', 'child_of', self.ids)]
        return action
