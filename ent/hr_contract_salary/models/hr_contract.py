# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import api, fields, http, models, _
from odoo.exceptions import ValidationError

from datetime import timedelta


class HrContract(models.Model):
    _inherit = 'hr.contract'

    origin_contract_id = fields.Many2one('hr.contract', string="Origin Contract", help="The contract from which this contract has been duplicated.")
    access_token = fields.Char('Security Token', copy=False)
    access_token_consumed = fields.Boolean('Consumed Access Token')
    access_token_end_date = fields.Date('Access Token Validity Date', copy=False)
    signature_request_ids = fields.Many2many('signature.request', string="Requested Signatures")
    signature_request_count = fields.Integer(compute='_compute_signature_request_count')
    active_employee = fields.Boolean(related='employee_id.active')
    signature_request_template_id = fields.Many2one('signature.request.template', string="Document Template",
        help="Contract template that the employee will have to sign.")

    @api.depends('signature_request_ids')
    def _compute_signature_request_count(self):
        for contract in self:
            contract.signature_request_count = len(contract.signature_request_ids)

    def configure_access_token(self):
        for contract in self:
            contract.access_token = uuid.uuid4().hex
            contract.access_token_end_date = contract._get_access_token_end_date()

    def _get_access_token_end_date(self):
        today = fields.Date.today()
        validity = self.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.access_token_validity', default=30)
        return fields.Date.to_string(fields.Date.from_string(today) + timedelta(days=validity))

    def action_accept_package(self):
        if self.origin_contract_id.employee_id:
            self.origin_contract_id.state = 'close'
        self.state = 'open'
        self.access_token_consumed = True
        self.employee_id.active = True
        if self.car_id:
            self.car_id.driver_id = self.employee_id.address_home_id

    def action_refuse_package(self):
        self.state = 'close'

    def open_package_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'name': "Redirect to the package configurator for an employee",
            'target': 'self',
            'url': "/salary_package/contract/%s" % (self.id,)
        }

    def open_signature_requests(self):
        self.ensure_one()
        if len(self.signature_request_ids.ids) == 1:
            return self.signature_request_ids.go_to_document()
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Signature Requests',
                'view_mode': 'tree,form',
                'res_model': 'signature.request',
                'domain': [('id', 'in', self.signature_request_ids.ids)]
            }

    def send_offer(self):
        self.ensure_one()
        if self.employee_id.address_home_id:
            try:
                template_id = self.env.ref('hr_contract_salary.mail_template_send_offer').id
            except ValueError:
                template_id = False
            try:
                compose_form_id = self.env.ref('mail.email_compose_message_wizard_form').id
            except ValueError:
                compose_form_id = False
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if self.employee_id.active:
                path = '/salary_package/contract/' + str(self.id)
            else:
                path = '/salary_package/contract/' + str(self.access_token)
            ctx = {
                'default_model': 'hr.contract',
                'default_res_id': self.ids[0],
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'salary_package_url': base_url + path,
                'custom_layout': "hr_contract_salary.mail_template_data_notification_email_send_offer",
            }
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(compose_form_id, 'form')],
                'view_id': compose_form_id,
                'target': 'new',
                'context': ctx,
            }
        else:
            raise ValidationError(_("No home address defined on the employee!"))
