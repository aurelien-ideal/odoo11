# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fiscalyear_last_day = fields.Integer(related='company_id.fiscalyear_last_day', default=31,
        help="The last day of the month will be taken if the chosen day doesn't exist.")
    fiscalyear_last_month = fields.Selection([
        (1, 'January'),
        (2, 'February'),
        (3, 'March'),
        (4, 'April'),
        (5, 'May'),
        (6, 'June'),
        (7, 'July'),
        (8, 'August'),
        (9, 'September'),
        (10, 'October'),
        (11, 'November'),
        (12, 'December')
        ], related='company_id.fiscalyear_last_month', default=12,
        help="The last day of the month will be taken if the chosen day doesn't exist.")
    period_lock_date = fields.Date(string='Lock Date for Non-Advisers',
                                   related='company_id.period_lock_date')
    fiscalyear_lock_date = fields.Date(string='Lock Date for All Users',
                                       related='company_id.fiscalyear_lock_date')
    use_anglo_saxon = fields.Boolean(string='Anglo-Saxon Accounting', related='company_id.anglo_saxon_accounting')
    transfer_account_id = fields.Many2one('account.account', string="Transfer Account",
        related='company_id.transfer_account_id',
        domain=lambda self: [('reconcile', '=', True), ('user_type_id.id', '=', self.env.ref('account.data_account_type_current_assets').id)],
        help="Intermediary account used when moving money from a liquidity account to another")

    @api.model
    def create(self, vals):
        vals['fiscalyear_last_day'] = self.company_id._verify_fiscalyear_last_day(
            vals.get('company_id'),
            vals.get('fiscalyear_last_day'),
            vals.get('fiscalyear_last_month'))
        return super(ResConfigSettings, self).create(vals)
