# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class Partner(models.Model):
    _inherit = 'res.partner'

    sdd_mandate_ids = fields.One2many(comodel_name='sdd.mandate', inverse_name='partner_id', help="Every mandate belonging to this partner.")
