# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class ir_actions_report(models.Model):
    _name = 'ir.actions.report'
    _inherit = ['studio.mixin', 'ir.actions.report']

    @api.multi
    def studio_edit(self):
        """ Returns the action when clicking on a report in the Studio kanban view.
            This client action needs the report associated view to customize it
                and all data needed to display the report.
        """
        self.ensure_one()
        action_ref = self.env.ref('web_studio.action_web_studio_report_editor')
        if not action_ref:
            return False
        action_data = action_ref.read()[0]

        # Report data
        action_data['id'] = self.id
        action_data['name'] = _('Customize : ') + self.name
        action_data['display_name'] = _('Customize : ') + self.display_name
        action_data['report_name'] = self.report_name
        action_data['report_file'] = self.report_file

        # View data
        report_name = self.report_name.split('.')[-1] if len(self.report_name.split('.')) > 1 else self.report_name
        associated_view = self.env['ir.ui.view'].search([('name', 'ilike', report_name), ('type', '=', 'qweb')], limit=1)
        action_data['view_id'] = associated_view.id

        # Records data
        action_data['active_ids'] = ','.join(str(x) for x in self.env[self.model].search([], limit=1).mapped('id'))

        return action_data
