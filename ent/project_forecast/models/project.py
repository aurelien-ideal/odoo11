# -*- coding: utf-8 -*-

from odoo import api, exceptions, fields, models, _


class Project(models.Model):
    _inherit = 'project.project'

    allow_forecast = fields.Boolean("Allow forecast", default=False, help="This feature shows the Forecast link in the kanban view")

    @api.multi
    def write(self, vals):
        if 'active' in vals:
            self.env['project.forecast'].with_context(active_test=False).search([('project_id', 'in', self.ids)]).write({'active': vals['active']})
        return super(Project, self).write(vals)

    @api.multi
    def view_monthly_forecast(self):
        self.env.cr.execute("""
            SELECT count(*)
            FROM project_forecast
            WHERE project_id = %s
              AND date_trunc('month', start_date) != date_trunc('month', end_date);
        """, [self.id])
        [count] = self.env.cr.fetchone()
        if count:
            raise exceptions.UserError(
                _("Can only be used for forecasts not spanning multiple months, "
                  "found %(forecast_count)d forecast(s) spanning across "
                  "months in %(project_name)s") % {
                    'forecast_count': count,
                    'project_name': self.display_name,
                }
            )
        context = dict(self.env.context, default_project_id=self.id, default_employee_id=self.user_id.employee_ids[0].id)
        # forecast grid requires start and end dates on the project
        if not (self.date_start and self.date):
            return {
                'name': self.display_name,
                'type': 'ir.actions.act_window',
                'res_model': 'project.project',
                'target': 'new',
                'res_id': self.id,
                'view_mode': 'form',
                'view_id': self.env.ref('project_forecast.view_project_set_dates').id,
                'context': context,
            }

        return {
            'name': _("Forecast"),
            'type': 'ir.actions.act_window',
            'res_model': 'project.forecast',
            'view_id': self.env.ref('project_forecast.project_forecast_grid').id,
            'view_mode': 'grid',
            'domain': [['project_id', '=', self.id]],
            'context': context,
        }


class Task(models.Model):
    _inherit = 'project.task'

    allow_forecast = fields.Boolean('Allow Forecast', readonly=True, related='project_id.allow_forecast', store=False)

    @api.multi
    def create_forecast(self):
        view_id = self.env.ref('project_forecast.project_forecast_view_form').id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.forecast',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
                'default_employee_id': self.user_id.employee_ids and self.user_id.employee_ids[0].id,
            }
        }
