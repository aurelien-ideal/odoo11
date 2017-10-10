# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.osv import expression


class Forecast(models.Model):

    _inherit = "project.forecast"

    effective_hours = fields.Float(string="Effective hours", compute='_compute_effective_hours', store=True)
    percentage_hours = fields.Float(string="Progress", compute='_compute_percentage_hours', store=True)
    order_line_id = fields.Many2one('sale.order.line', string='Sales Order Line', related="task_id.sale_line_id", store=True)

    @api.one
    @api.depends('resource_hours', 'effective_hours')
    def _compute_percentage_hours(self):
        if self.resource_hours:
            self.percentage_hours = self.effective_hours / self.resource_hours
        else:
            self.percentage_hours = 0

    @api.one
    @api.depends('task_id', 'user_id', 'start_date', 'end_date', 'project_id.analytic_account_id')
    def _compute_effective_hours(self):
        if not self.task_id and not self.project_id:
            self.effective_hours = 0
        else:
            aac_obj = self.env['account.analytic.line']
            aac_domain = [
                ('user_id', '=', self.user_id.id),
                ('date', '>=', self.start_date),
                ('date', '<=', self.end_date)
            ]
            if self.task_id:
                timesheets = aac_obj.search(expression.AND([[('task_id', '=', self.task_id.id)], aac_domain]))
            elif self.project_id:
                timesheets = aac_obj.search(expression.AND([[('account_id', '=', self.project_id.analytic_account_id.id)], aac_domain]))
            else:
                timesheets = aac_obj.browse()

            self.effective_hours = sum(timesheet.unit_amount for timesheet in timesheets)
