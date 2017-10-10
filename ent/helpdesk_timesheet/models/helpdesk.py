# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    project_id = fields.Many2one("project.project", string="Project")

    @api.model
    def create(self, vals):
        if vals.get('use_helpdesk_timesheet') and not vals.get('project_id'):
            vals['project_id'] = self.env['project.project'].create({
                'name': vals['name'],
                'type_ids': [
                    (0, 0, {'name': _('In Progress')}),
                    (0, 0, {'name': _('Closed'), 'is_closed': True})
                ]
            }).id
        return super(HelpdeskTeam, self).create(vals)

    @api.multi
    def write(self, vals):
        if 'use_helpdesk_timesheet' in vals and not vals['use_helpdesk_timesheet']:
            vals['project_id'] = False
        result = super(HelpdeskTeam, self).write(vals)
        for team in self.filtered(lambda team: team.use_helpdesk_timesheet and not team.project_id):
            team.project_id = self.env['project.project'].create({
                'name': team.name,
                'type_ids': [
                    (0, 0, {'name': _('In Progress')}),
                    (0, 0, {'name': _('Closed'), 'is_closed': True})
                ]
            })
        return result


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    @api.model
    def default_get(self, fields_list):
        result = super(HelpdeskTicket, self).default_get(fields_list)
        if result.get('team_id') and not result.get('project_id'):
            result['project_id'] = self.env['helpdesk.team'].browse(result['team_id']).project_id.id
        return result

    project_id = fields.Many2one("project.project", string="Project")
    task_id = fields.Many2one("project.task", string="Task", domain="[('project_id', '=', project_id)]", track_visibility="onchange", help="The task must have the same customer as this ticket.")
    timesheet_ids = fields.One2many('account.analytic.line', 'helpdesk_ticket_id', 'Timesheets')
    is_closed = fields.Boolean(related="task_id.stage_id.is_closed", string="Is Closed", readonly=True)
    is_task_active = fields.Boolean(related="task_id.active", readonly=True)
    use_helpdesk_timesheet = fields.Boolean('Timesheet activated on Team', related='team_id.use_helpdesk_timesheet', readonly=True)

    @api.onchange('partner_id', 'project_id')
    def _onchange_partner_project(self):
        if self.project_id:
            domain = [('project_id', '=', self.project_id.id)]
            if self.partner_id:
                domain.append(('partner_id', '=', self.partner_id.id))
                # Take the latest task of the selected customer and set it.
                self.task_id = self.env['project.task'].search(domain, limit=1)
            else:
                self.task_id = None
            return {'domain': {'task_id': domain}}

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.timesheet_ids:
            if self.task_id:
                msg = _("All timesheet hours will be assigned to the selected task on save. Discard to avoid the change.")
            else:
                msg = _("Timesheet hours will not be assigned to a customer task. Set a task to charge a customer.")
            return {'warning':
                {
                    'title': _("Warning"),
                    'message': msg
                }
            }

    @api.multi
    def write(self, values):
        result = super(HelpdeskTicket, self).write(values)
        if 'task_id' in values:
            self.sudo().mapped('timesheet_ids').write({'task_id': values['task_id']})  # sudo since helpdesk user can change task
        return result

    @api.multi
    def action_view_ticket_task(self):
        self.ensure_one()
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'res_id': self.task_id.id,
        }
