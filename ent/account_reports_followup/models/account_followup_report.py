# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.tools.translate import _
import time
import math


class account_report_followup_all(models.AbstractModel):
    _inherit = "account.followup.report.all"

    def get_partners_in_need_of_action(self, options):
        partners_data = self.env['res.partner'].get_partners_in_need_of_action_and_update()
        options['partner_followup_level'] = partners_data
        if options.get('type_followup') == 'action':
            return self.env['res.partner'].browse(partners_data)
        return super(account_report_followup_all, self).get_partners_in_need_of_action(options)


class account_report_followup(models.AbstractModel):
    _inherit = "account.followup.report"

    def get_followup_line(self, options):
        if options.get('partner_id') and options.get('partner_followup_level') and options['partner_followup_level'].get(options.get('partner_id')):
            followup_line = self.env['account_followup.followup.line'].browse(options['partner_followup_level'][options['partner_id']][0])
            return followup_line
        elif self.env.context.get('followup_line_id'):
            followup_line = self.env['account_followup.followup.line'].browse(self.env.context.get('followup_line_id'))
            return followup_line
        else:
            return False

    def get_default_summary(self, options):
        followup_line = self.get_followup_line(options)
        if followup_line:
            partner = self.env['res.partner'].browse(options['partner_id'])
            summary = followup_line.description
            try:
                summary = summary % {'partner_name': partner.name,
                                               'date': time.strftime('%Y-%m-%d'),
                                               'user_signature': self.env.user.signature or '',
                                               'company_name': self.env.user.company_id.name}
            except ValueError as e:
                message = "An error has occurred while formatting your followup letter/email. (Lang: %s, Followup Level: #%s) \n\nFull error description: %s" \
                          % (partner.lang, followup_line.id, e)
                raise ValueError(message)
            return summary
        else:
            return self.env.user.company_id.overdue_msg or self.env['res.company'].default_get(['overdue_msg'])['overdue_msg']

    def get_post_message(self, options):
        res = super(account_report_followup, self).get_post_message(options)
        followup_line = self.get_followup_line(options)
        if followup_line:
            res += ' - ' + _('Level: ') + followup_line.name
        return res

    def get_report_value(self, partner, options):
        report_value = super(account_report_followup, self).get_report_value(partner, options)
        options['partner_id'] = partner.id
        report_value['followup_line'] = self.get_followup_line(options)
        return report_value

    @api.model
    def do_manual_action(self, options):
        followup_line = self.get_followup_line(options)
        msg = _('Manual action done')
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        if followup_line:
            msg += '\n' + followup_line.manual_action_note
        partner.message_post(body=msg, subtype='account_reports.followup_logged_action')
