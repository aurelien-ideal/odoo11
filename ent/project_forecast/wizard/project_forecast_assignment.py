# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class Assignment(models.TransientModel):
    _name = 'project.forecast.assignment'

    project_id = fields.Many2one('project.project', string="Project", required=True)
    task_id = fields.Many2one('project.task', string="Task", required=True,
                              domain="[('project_id', '=', project_id)]")
    employee_id = fields.Many2one('hr.employee', "Employee", required=True)

    @api.multi
    def create_assignment(self):
        # create a project.forecast on the project's first month
        project_start = fields.Date.from_string(self.project_id.date_start)
        month_start = fields.Date.to_string(project_start + relativedelta(day=1))
        month_end = fields.Date.to_string(project_start + relativedelta(months=1, day=1, days=-1))

        self.env['project.forecast'].create({
            'project_id': self.project_id.id,
            'task_id': self.task_id.id,
            'employee_id': self.employee_id.id,
            'start_date': month_start,
            'end_date': month_end,
            'time': 0,
        })

        return {'type': 'ir.actions.act_window_close'}
