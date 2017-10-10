# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import babel
from dateutil.relativedelta import relativedelta

from odoo import http, fields, _
from odoo.http import request
from odoo.osv import expression
from odoo.tools import float_round

from odoo.addons.sale_timesheet.controllers.main import SaleTimesheetController


DEFAULT_MONTH_RANGE = 3


class TimesheetForecastController(SaleTimesheetController):

    def _apply_on_forecast(self, domain):
        """ Check if the (timesheet) domain also applied on forecast. Use `expression`
            to check the applicability without doing SQL query.
        """
        try:
            expression.expression(domain, request.env['project.forecast'])
            return True
        except ValueError:
            return False

    def _prepare_plan_values(self, domain):
        values = super(TimesheetForecastController, self)._prepare_plan_values(domain)

        # if the domain does not apply also on forecast, do nothing
        if not self._apply_on_forecast(domain) or not values['timesheet_lines']:
            return values

        # -- Table comparing timesheet and forecast
        # starting from the last timesheet date, build the date ranges for timesheet and forecast
        initial_date = fields.Date.from_string(max([line.date for line in values['timesheet_lines']])).replace(day=1)
        ts_months = sorted([fields.Date.to_string(initial_date-relativedelta(months=i)) for i in range(0, DEFAULT_MONTH_RANGE)])
        fc_months = sorted([fields.Date.to_string(initial_date+relativedelta(months=i)) for i in range(0, DEFAULT_MONTH_RANGE)])

        timesheet_forecast_data = self._plan_get_timesheet_forecast_data(domain, ts_months, fc_months)

        so_line_ids = [sol_name_get[0] for sol_name_get in timesheet_forecast_data if sol_name_get]
        so_sol_mapping = {sol.id: sol.order_id.name_get()[0] for sol in request.env['sale.order.line'].sudo().browse(so_line_ids)}

        timesheet_forecast_values = {}
        for sol_name_get, sol_line_value in timesheet_forecast_data.items():
            order_name_get = so_sol_mapping.get(sol_name_get[0])
            timesheet_forecast_values.setdefault(order_name_get, self._get_default_line_dict(ts_months, fc_months))
            # add sol line in the groupment of the SO
            timesheet_forecast_values[order_name_get]['lines'][sol_name_get] = sol_line_value
            for ts_slot in ts_months + ['total']:
                timesheet_forecast_values[order_name_get]['timesheet'][ts_slot] += sol_line_value['timesheet'][ts_slot]
            for fc_slot in fc_months + ['total']:
                timesheet_forecast_values[order_name_get]['forecast'][fc_slot] += sol_line_value['forecast'][fc_slot]

        sol_task_planned_hour_mapping = {task.sudo().sale_line_id.id: task.planned_hours for task in request.env['project.task'].search([('sale_line_id', 'in', so_line_ids)])}

        # built the table : headers and rows

        def _to_short_month_name(date):
            month_index = fields.Date.from_string(date).month
            return babel.dates.get_month_names('abbreviated', locale=request.env.context.get('lang', 'en_US'))[month_index]

        header = [_('Name')] + [_to_short_month_name(date) for date in ts_months] + [_('Done')] + [_to_short_month_name(date) for date in fc_months] + [_('Forecasted'), _('Planned'), _('Remaining')]

        rows = []
        # also compute planned hours (from task), and remaining hours as 'planned hours' - timesheeted - forecasted
        for order_name_get, order_vals in timesheet_forecast_values.items():
            # SO row
            so_row = [order_name_get[1]]
            so_row += [order_vals['timesheet'].get(ts_m) for ts_m in ts_months + ['total']]
            so_row += [order_vals['forecast'].get(fc_m) for fc_m in fc_months + ['total']]
            rows.append({'row_values': so_row, 'meta': {'type': 'sale_order', 'res_model': 'sale.order', 'res_id': order_name_get[0]}})
            # SO Lines rows
            total_planned_hours = 0.0
            total_remaining_hours = 0.0
            for sol_name_get, sol_vals in order_vals['lines'].items():
                sol_row = [sol_name_get[1]]
                sol_row += [sol_vals['timesheet'].get(ts_m) for ts_m in ts_months + ['total']]
                sol_row += [sol_vals['forecast'].get(fc_m) for fc_m in fc_months + ['total']]
                sol_planned_hours = sol_task_planned_hour_mapping.get(sol_name_get[0], 0.0)
                sol_remaining_hours = sol_planned_hours - sol_row[DEFAULT_MONTH_RANGE + 1]
                sol_row += [sol_planned_hours, sol_remaining_hours]
                total_planned_hours += sol_planned_hours
                total_remaining_hours += sol_remaining_hours
                rows.append({'row_values': sol_row, 'meta': {'type': 'sale_order_line', 'res_model': 'sale.order.line', 'res_id': sol_name_get[0]}})
                # employee rows
                for empl_name_get, empl_vals in sol_vals['lines'].items():
                    empl_row = [empl_name_get[1]]
                    empl_row += [empl_vals['timesheet'].get(ts_m) for ts_m in ts_months + ['total']]
                    empl_row += [empl_vals['forecast'].get(fc_m) for fc_m in fc_months + ['total']]
                    empl_row += ['', '']  # empty planned for employee
                    rows.append({'row_values': empl_row, 'meta': {'type': 'hr_employee', 'res_model': 'hr.employee', 'res_id': empl_name_get[0]}})
            so_row += [total_planned_hours, total_remaining_hours]

        values['timesheet_forecast_table'] = {
            'header': header,
            'rows': rows,
            'attrs': {
                'timesheet_col_index': DEFAULT_MONTH_RANGE + 1,  # 1 is for the first column (name)
                'forecast_col_index': 2 * (DEFAULT_MONTH_RANGE + 1),
            }
        }

        return values

    def _plan_get_timesheet_forecast_data(self, domain, timesheet_months, forecast_months):
        """ Compute timesheet and forecast value, grouped by SO line.
            :param domain: a domain (list) applied to both account.analytic.line and project.forecast models
            :param timesheet_months :  list of date (in ORM format) of first day timesheet months
            :param forecast_months : list of date (in ORM format) of first day forecast months
            Get forecast value in the format :
            {
                so_line_id: {
                    'lines': {
                        employee_id_1: {
                            'timesheet': {
                                '2017-02-01': 0.0, # sum of unit_amount of month timesheet
                                '2017-03-01': 0.0,
                                '2017-04-01': 0.0
                                'total': 0.0,
                            },
                            'forecast': {
                                '2017-05-01': 0.0, # sum of resource_hours of month forecast
                                '2017-06-01': 0.0,
                                '2017-04-01': 0.0
                                'total': 0.0,
                            },
                        }
                    },
                    'timesheet': {
                        '2017-02-01': 0.0,
                        '2017-03-01': 0.0,
                        '2017-04-01': 0.0,
                        'total': 0.0,
                    },
                    'forecast': {
                        '2017-05-01': 0.0,
                        '2017-06-01': 0.0,
                        '2017-04-01': 0.0,
                        'total': 0.0,
                    },
                }
            }
        """
        hour_rounding = request.env.ref('product.product_uom_hour').rounding
        # default values (per task per employee)
        result = {}

        # use _read_group_raw to get date range
        fc_max_month_date = fields.Date.from_string(max(forecast_months))+relativedelta(months=1)
        fc_domain = domain + [('order_line_id', '!=', False), ('start_date', '>=', min(forecast_months)), ('start_date', '<', fields.Date.to_string(fc_max_month_date))]
        data_forecast = request.env['project.forecast'].sudo()._read_group_raw(fc_domain, ['order_line_id', 'resource_hours', 'employee_id', 'start_date'], ['start_date:month', 'order_line_id', 'employee_id'], lazy=False)
        for forecast_row in data_forecast:
            current_date = forecast_row['start_date:month'][0].split('/')[0]
            resource_hours = float_round(forecast_row['resource_hours'], precision_rounding=hour_rounding)
            result.setdefault(forecast_row['order_line_id'], self._get_default_line_dict(timesheet_months, forecast_months))
            # compute value per date and total, per employee
            result[forecast_row['order_line_id']]['lines'].setdefault(forecast_row['employee_id'], self._get_default_line_dict(timesheet_months, forecast_months, is_leaf=True))['forecast'][current_date] = resource_hours
            result[forecast_row['order_line_id']]['lines'][forecast_row['employee_id']]['forecast']['total'] += resource_hours
            # increase the total of the SO line
            result[forecast_row['order_line_id']]['forecast'][current_date] += resource_hours
            result[forecast_row['order_line_id']]['forecast']['total'] += resource_hours

        # use _read_group_raw to get date range
        ts_max_month_date = fields.Date.from_string(max(timesheet_months))+relativedelta(months=1)
        ts_domain = domain + [('so_line', '!=', False), ('date', '<', fields.Date.to_string(ts_max_month_date)), ('date', '>=', min(timesheet_months))]
        data_timesheet = request.env['account.analytic.line'].sudo()._read_group_raw(ts_domain, ['so_line', 'unit_amount', 'employee_id', 'date'], ['date:month', 'so_line', 'employee_id'], lazy=False)
        for timesheet_row in data_timesheet:
            current_date = timesheet_row['date:month'][0].split('/')[0]
            unit_amount = float_round(timesheet_row['unit_amount'], precision_rounding=hour_rounding)
            result.setdefault(timesheet_row['so_line'], self._get_default_line_dict(timesheet_months, forecast_months))
            # compute value per date and total, per employee
            result[timesheet_row['so_line']]['lines'].setdefault(timesheet_row['employee_id'], self._get_default_line_dict(timesheet_months, forecast_months, is_leaf=True))['timesheet'][current_date] = unit_amount
            result[timesheet_row['so_line']]['lines'][timesheet_row['employee_id']]['timesheet']['total'] += unit_amount
            # increase the total of the SO line
            result[timesheet_row['so_line']]['timesheet'][current_date] += unit_amount
            result[timesheet_row['so_line']]['timesheet']['total'] += unit_amount
        return result

    def _get_default_line_dict(self, timesheet_months, forecast_months, is_leaf=False):
        """ Return an empty line for the timesheet/forecast array structure. It looks like
            {
                'lines': {},  # only if is_leaf == False, otherwise, their is no key 'lines'
                'timesheet': {
                    '2017-02-01': 0.0,
                    '2017-03-01': 0.0,
                    '2017-04-01': 0.0
                    'total': 0.0,
                },
                'forecast': {
                    '2017-05-01': 0.0,
                    '2017-06-01': 0.0,
                    '2017-04-01': 0.0
                    'total': 0.0,
                }
            }
        """
        result = {
            'timesheet': dict.fromkeys(timesheet_months + ['total'], 0.0),
            'forecast': dict.fromkeys(forecast_months + ['total'], 0.0),
        }
        if not is_leaf:
            result['lines'] = {}
        return result

    def _plan_get_stat_button(self, timesheet_lines):
        stat_buttons = super(TimesheetForecastController, self)._plan_get_stat_button(timesheet_lines)

        stat_project_ids = timesheet_lines.mapped('project_id').ids
        stat_forecast_domain = [('project_id', 'in', stat_project_ids)]
        stat_buttons.append({
            'name': _('Forecast'),
            'count': request.env['project.forecast'].search_count(stat_forecast_domain),
            'res_model': 'project.forecast',
            'domain': stat_forecast_domain,
            'icon': 'fa fa-tasks',
        })
        return stat_buttons

    @http.route('/timesheet/plan/action', type='json', auth="user")
    def plan_stat_button(self, domain, res_model='account.analytic.line'):
        action = super(TimesheetForecastController, self).plan_stat_button(domain, res_model=res_model)
        if res_model == 'project.forecast':
            action = request.env.ref('project_forecast.action_project_forecast_grid_by_project').read()[0]
            action.update({
                'name': _('Forecast'),
                'domain': domain,
                'context': request.env.context,  # erase original context to avoid default filter
            })
        return action
