# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_round


class Employee(models.Model):
    _inherit = 'hr.employee'

    timesheet_validated = fields.Date(
        "Timesheets Validation Date",
        help="Date until which the employee's timesheets have been validated")
    timesheet_manager_id = fields.Many2one(
        'res.users', string='Timesheet Responsible',
        domain=lambda self: [('groups_id', 'in', self.env.ref('hr_timesheet.group_timesheet_manager').id)],
        help="User responsible of timesheet validation. Should be Timesheet Manager.")

    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        if self.parent_id:
            self.timesheet_manager_id = self.parent_id.user_id

    @api.multi
    def get_timesheet_and_working_hours(self, date_start, date_stop):
        """ Get the difference between the supposed working hour (based on resource calendar) and
            the timesheeted hours, for the given period `date_start` - `date_stop`.
            :param date_start : start date of the period to check (string)
            :param date_stop : end date of the period to check (string)
            :returns dict : a dict mapping the employee_id with his timesheeted and working hours for the
                given period.
        """
        employees = self.filtered(lambda emp: emp.resource_calendar_id)
        result = dict.fromkeys(self.ids, dict(timesheet_hours=0.0, working_hours=0.0, date_start=date_start, date_stop=date_stop))
        if not employees:
            return result

        # find timesheeted hours of employees with working hours
        self.env.cr.execute("""
            SELECT A.employee_id as employee_id, sum(A.unit_amount) as amount_sum
            FROM account_analytic_line A
            WHERE A.employee_id IN %s AND date >= %s AND date <= %s
            GROUP BY A.employee_id
        """, (tuple(employees.ids), date_start, date_stop))
        for data_row in self.env.cr.dictfetchall():
            result[data_row['employee_id']]['timesheet_hours'] = float_round(data_row['amount_sum'], 2)

        # find working hours for the given period of employees with working calendar
        for employee in employees:
            working_hours = employee.resource_calendar_id.get_work_hours_count(
                fields.Datetime.from_string(date_start),
                fields.Datetime.from_string(date_stop),
                compute_leaves=False, resource_id=employee.resource_id.id
            )
            result[employee.id]['working_hours'] = float_round(working_hours, 2)
        return result
