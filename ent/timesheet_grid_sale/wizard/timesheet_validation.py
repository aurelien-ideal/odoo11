# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.osv import expression


class ValidationWizard(models.TransientModel):
    _inherit = 'timesheet.validation'

    @api.multi
    def action_validate(self):
        """ Recompute SO Lines delivered at validation """
        # As super will change the "timesheet_validated" field of a
        # "validable_employee", we have to get the min date before
        # calling super().
        validable_employees = self.validation_line_ids.filtered('validate').mapped('employee_id')
        oldest_last_validation_date = None
        if validable_employees:
            oldest_last_validation_date = min(validable_employees.mapped('timesheet_validated'))
        res = super(ValidationWizard, self).action_validate()

        # normally this would be done through a computed field, or triggered
        # by the recomputation of self.validated or something, but that does
        # not seem to be an option, and this is apparently the way to force
        # the recomputation of qty_delivered on sale_order_line
        # cf sale.sale_analytic, sale.sale.SaleOrderLine._get_to_invoice_qty
        # look for the so_line of all timesheet lines associated with the
        # same users as the validable employees (as they're all implicitly going
        # to be validated by the current validation), then recompute their
        # analytics. Semantically we should roundtrip through employee_ids,
        # but that's an o2m so (lines).mapped('user_id.employee_ids.user_id')
        # should give the same result as (lines).mapped('user_id')
        domain = expression.AND([
            [('is_timesheet', '=', True)],
            [('employee_id', 'in', validable_employees.ids)]
        ])
        if oldest_last_validation_date:
            domain = expression.AND([
                domain,
                [('date', '>', oldest_last_validation_date)]
            ])
        self.env['account.analytic.line'].sudo().search(domain).mapped('so_line')._analytic_compute_delivered_quantity()

        return res
