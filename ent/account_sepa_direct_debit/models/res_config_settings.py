# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sdd_creditor_identifier = fields.Char(related='company_id.sdd_creditor_identifier', string='Creditor identifier', help='Creditor identifier of your company withing SEPA scheme.')
