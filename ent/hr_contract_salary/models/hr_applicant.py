# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    default_contract_id = fields.Many2one(related='job_id.default_contract_id')
    proposed_contracts = fields.Many2many('hr.contract', string="Proposed Contracts")
    proposed_contracts_count = fields.Integer(compute="_compute_proposed_contracts_count", string="Proposed Contracts Count")

    def _compute_proposed_contracts_count(self):
        for applicant in self:
            applicant.proposed_contracts_count = len(applicant.proposed_contracts)

    def create_offer(self):
        name = self.partner_name or self.partner_id.name or self.name or 'new employee'

        if not self.partner_id:
            new_partner = self.env['res.partner'].create({
                'name': name,
                'country_id': self.env.ref('base.be').id,
            })
            self.partner_id = new_partner
        else:
            new_partner = self.partner_id

        if not self.emp_id:
            new_employee = self.env['hr.employee'].create({
                'name': name,
                'active': False,
                'country_id': self.env.ref('base.be').id,
                'address_home_id': new_partner.id,
            })
            self.emp_id = new_employee
        else:
            new_employee = self.emp_id

        new_contract = self.default_contract_id.copy({
            'name': self.default_contract_id.name + ' - ' + new_employee.name,
            'employee_id': new_employee.id,
            'origin_contract_id': self.default_contract_id.id,
        })

        partners_to_subscribe = [new_partner.id]
        if self.user_id:
            partners_to_subscribe.append(self.user_id.partner_id.id)
        new_contract.message_subscribe(partner_ids=partners_to_subscribe)

        new_contract.configure_access_token()

        self.proposed_contracts += new_contract

        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.contract",
            "views": [[False, "form"]],
            "res_id": new_contract.id,
        }

    def action_show_proposed_contracts(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.contract",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["employee_id", "=", self.emp_id.id]],
            "name": "Proposed Contracts",
        }
