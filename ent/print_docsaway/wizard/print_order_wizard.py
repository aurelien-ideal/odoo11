# -*- coding: utf-8 -*-
from odoo import api, models

from odoo.addons.print_docsaway.models.print_docsaway import DOCSAWAY_CURRENCIES_CODE


class PrintOrderWizard(models.TransientModel):

    _inherit = 'print.order.wizard'

    @api.onchange('provider_id')
    def _onchange_provider_id(self):
        result = super(PrintOrderWizard, self)._onchange_provider_id()
        if self.provider_id.provider == 'docsaway':
            if self.provider_currency_id.name not in DOCSAWAY_CURRENCIES_CODE:  # Set the default docsaway currency
                self.provider_currency_id = self.env['res.currency'].sudo().with_context(active_test=False).search([('name', '=', 'AUD')])
            return {'domain': {'currency_id': [('name', 'in', DOCSAWAY_CURRENCIES_CODE)]}}
        return result
