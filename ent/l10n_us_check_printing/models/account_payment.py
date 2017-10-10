# -*- coding: utf-8 -*-

from odoo import models, api, _

class account_payment(models.Model):
    _inherit = "account.payment"

    @api.multi
    def do_print_checks(self):
        us_check_layout = self[0].company_id.us_check_layout
        if us_check_layout != 'disabled':
            self.write({'state': 'sent'})
            return self.env.ref(us_check_layout).report_action(self)
        return super(account_payment, self).do_print_checks()
