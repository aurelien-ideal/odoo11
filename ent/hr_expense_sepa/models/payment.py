# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrExpenseSheetRegisterPaymentWizard(models.TransientModel):
    _inherit = "hr.expense.sheet.register.payment.wizard"

    payment_method_code = fields.Char(related='payment_method_id.code',
                                      help="Technical field used to adapt the interface to the payment type selected.",
                                      readonly=True)
    partner_bank_account_id = fields.Many2one('res.partner.bank', string="Recipient Bank Account")

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        active_ids = self._context.get('active_ids', [])
        expense_sheet = self.env['hr.expense.sheet'].browse(active_ids)
        if expense_sheet.employee_id.id and expense_sheet.employee_id.sudo().bank_account_id.id:
            self.partner_bank_account_id = expense_sheet.employee_id.sudo().bank_account_id.id
        elif self.partner_id and len(self.partner_id.bank_ids) > 0:
            self.partner_bank_account_id = self.partner_id.bank_ids[0]
        else:
            self.partner_bank_account_id = False

    def _get_payment_vals(self):
        res = super(HrExpenseSheetRegisterPaymentWizard, self)._get_payment_vals()
        if self.payment_method_id == self.env.ref('account_sepa.account_payment_method_sepa_ct'):
            res.update({'partner_bank_account_id': self.partner_bank_account_id.id})
        return res
