# -*- coding: utf-8 -*-

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import pycompat


class ProjectForecast(models.Model):
    _name = 'project.forecast'

    def _default_employee_id(self):
        user_id = self.env.context.get('default_user_id', self.env.uid)
        employee_ids = self.env['hr.employee'].search([('user_id', '=', user_id)])
        return employee_ids and employee_ids[0] or False

    def default_end_date(self):
        return date.today() + timedelta(days=1)

    def _read_group_employee_ids(self, employee, domain, order):
        group = self.env.ref('project.group_project_user', False) or self.env.ref('base.group_user')
        return self.env['hr.employee'].search([('user_id', 'in', group.users.ids)])

    name = fields.Char(compute='_compute_name')
    active = fields.Boolean(default=True)
    employee_id = fields.Many2one('hr.employee', "Employee", default=_default_employee_id, required=True, group_expand='_read_group_employee_ids')
    user_id = fields.Many2one('res.users', string="User", related='employee_id.user_id', store=True, readonly=True)
    project_id = fields.Many2one('project.project', string="Project")
    task_id = fields.Many2one(
        'project.task', string="Task", domain="[('project_id', '=', project_id)]",
        group_expand='_read_forecast_tasks')

    # used in custom filter
    stage_id = fields.Many2one(related='task_id.stage_id', string="Task stage")
    tag_ids = fields.Many2many(related='task_id.tag_ids', string="Task tags")

    time = fields.Float(string="%", help="Percentage of working time", compute='_compute_time', store=True, digits=(16, 2))

    start_date = fields.Date(default=fields.Date.today, required="True")
    end_date = fields.Date(default=default_end_date, required="True")

    # consolidation color and exclude
    color = fields.Integer(string="Color", compute='_compute_color')
    exclude = fields.Boolean(string="Exclude", compute='_compute_exclude', store=True)

    # resource
    resource_hours = fields.Float(string="Planned hours", default=0)

    @api.one
    @api.depends('project_id', 'task_id', 'employee_id')
    def _compute_name(self):
        group = self.env.context.get("group_by", "")

        name = []
        if "employee_id" not in group:
            name.append(self.employee_id.name)
        if ("project_id" not in group and self.project_id):
            name.append(self.project_id.name)
        if ("task_id" not in group and self.task_id):
            name.append(self.task_id.name)

        if name:
            self.name = " - ".join(name)
        else:
            self.name = _("undefined")

    @api.one
    @api.depends('project_id.color')
    def _compute_color(self):
        self.color = self.project_id.color or 0

    @api.one
    @api.depends('project_id.name')
    def _compute_exclude(self):
        self.exclude = (self.project_id.name == "Leaves")

    @api.one
    @api.depends('resource_hours', 'start_date', 'end_date', 'employee_id.resource_calendar_id')
    def _compute_time(self):
        start = fields.Datetime.from_string(self.start_date)
        stop = fields.Datetime.from_string(self.end_date).replace(hour=23, minute=59, second=59, microsecond=999999)
        if self.employee_id.resource_calendar_id:
            hours = self.employee_id.resource_calendar_id.get_work_hours_count(start, stop, False, compute_leaves=False)
            if hours == 0:
                raise UserError(_("You cannot set a user with no working time."))
            self.time = self.resource_hours * 100.0 / hours
        else:
            self.time = 0

    @api.one
    @api.constrains('resource_hours')
    def _check_time_positive(self):
        if self.resource_hours and (self.resource_hours < 0):
            raise ValidationError(_("Forecasted time must be positive"))

    @api.one
    @api.constrains('task_id', 'project_id')
    def _task_id_in_project(self):
        if self.project_id and self.task_id and (self.task_id not in self.project_id.tasks):
            raise ValidationError(_("Your task is not in the selected project."))

    @api.one
    @api.constrains('start_date', 'end_date')
    def _start_date_lower_end_date(self):
        if self.start_date > self.end_date:
            raise ValidationError(_("The start-date must be lower than end-date."))

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id:
            self.project_id = self.task_id.project_id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        domain = [] if not self.project_id else [('project_id', '=', self.project_id.id)]
        return {
            'domain': {'task_id': domain},
        }

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.end_date < self.start_date:
            start = fields.Date.from_string(self.start_date)
            duration = timedelta(days=1)
            self.end_date = start + duration

    @api.onchange('end_date')
    def _onchange_end_date(self):
        if self.start_date > self.end_date:
            end = fields.Date.from_string(self.end_date)
            duration = timedelta(days=1)
            self.start_date = end - duration

    def _grid_start_of(self, span, step, anchor):
        if span != 'project':
            return super(ProjectForecast, self)._grid_start_of(span, step, anchor)

        if self.env.context.get('default_project_id'):
            project = self.env['project.project'].browse(self.env.context['default_project_id'])
        elif self.env.context.get('default_task_id'):
            project = self.env['project.task'].browse(self.env.context['default_task_id']).project_id

        if step != 'month':
            raise exceptions.UserError(
                _("Forecasting over a project only supports monthly forecasts (got step {})").format(step)
            )
        if not project.date_start:
            raise exceptions.UserError(
                _("A project must have a start date to use a forecast grid, "
                  "found no start date for {project.display_name}").format(
                    project=project
                )
            )
        return fields.Date.from_string(project.date_start).replace(day=1)

    def _grid_end_of(self, span, step, anchor):
        if span != 'project':
            return super(ProjectForecast, self)._grid_end_of(span, step, anchor)

        if self.env.context.get('default_project_id'):
            project = self.env['project.project'].browse(self.env.context['default_project_id'])
        elif self.env.context.get('default_task_id'):
            project = self.env['project.task'].browse(self.env.context['default_task_id']).project_id

        if not project.date:
            raise exceptions.UserError(
                _("A project must have an end date to use a forecast grid, "
                  "found no end date for {project.display_name}").format(
                    project=project
                )
            )
        return fields.Date.from_string(project.date)

    def _grid_pagination(self, field, span, step, anchor):
        if span != 'project':
            return super(ProjectForecast, self)._grid_pagination(field, span, step, anchor)
        return False, False

    @api.multi
    def adjust_grid(self, row_domain, column_field, column_value, cell_field, change):
        if column_field != 'start_date' or cell_field != 'resource_hours':
            raise exceptions.UserError(
                _("Grid adjustment for project forecasts only supports the "
                  "'start_date' columns field and the 'resource_hours' cell "
                  "field, got respectively %(column_field)r and "
                  "%(cell_field)r") % {
                    'column_field': column_field,
                    'cell_field': cell_field,
                }
            )

        from_, to_ = pycompat.imap(fields.Date.from_string, column_value.split('/'))
        start = fields.Date.to_string(from_)
        # range is half-open get the actual end date
        end = fields.Date.to_string(to_ - relativedelta(days=1))

        # see if there is an exact match
        cell = self.search(expression.AND([row_domain, [
            '&',
            ['start_date', '=', start],
            ['end_date', '=', end]
        ]]), limit=1)
        # if so, adjust in-place
        if cell:
            cell[cell_field] += change
            return False

        # otherwise copy an existing cell from the row, ignore eventual
        # non-monthly forecast
        # TODO: maybe expand the non-monthly forecast to a fully monthly forecast?
        self.search(row_domain, limit=1).ensure_one().copy({
            'start_date': start,
            'end_date': end,
            cell_field: change,
        })
        return False

    @api.multi
    def project_forecast_assign(self):
        # necessary to forward the default_project_id, otherwise it's
        # stripped out by the context forwarding of actions execution
        [action] = self.env.ref('project_forecast.action_project_forecast_assign').read()

        action['context'] = {
            'default_project_id': self.env.context.get('default_project_id'),
            'default_task_id': self.env.context.get('default_task_id')
        }
        return action

    @api.model
    def _read_forecast_tasks(self, tasks, domain, order):
        tasks_domain = [('id', 'in', tasks.ids)]
        if 'default_project_id' in self.env.context:
            tasks_domain = expression.OR([
                tasks_domain,
                [('project_id', '=', self.env.context['default_project_id'])]
            ])
        return tasks.sudo().search(tasks_domain, order=order)
