# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_round

from .taxcloud_request import TaxCloudRequest

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def action_confirm(self):
        res = True
        if self.fiscal_position_id.is_taxcloud:
            res = self.validate_taxes_on_sales_order()
        super(SaleOrder, self).action_confirm()
        return res

    @api.multi
    def validate_taxes_on_sales_order(self):
        Param = self.env['ir.config_parameter']
        api_id = Param.sudo().get_param('account_taxcloud.taxcloud_api_id')
        api_key = Param.sudo().get_param('account_taxcloud.taxcloud_api_key')
        request = TaxCloudRequest(api_id, api_key)

        shipper = self.company_id or self.env.user.company_id
        request.set_location_origin_detail(shipper)
        request.set_location_destination_detail(self.partner_shipping_id)

        request.set_order_items_detail(self)

        response = request.get_all_taxes_values()

        if response.get('error_message'):
            raise ValidationError(response['error_message'])

        tax_values = response['values']

        raise_warning = False
        for index, line in enumerate(self.order_line):
            if line.price_unit >= 0.0:
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0) * line.product_uom_qty
                if not price:
                    tax_rate = 0.0
                else:
                    tax_rate = tax_values[index] / price * 100
                if len(line.tax_id.ids) > 1 or float_compare(line.tax_id.amount, tax_rate, precision_digits=2):
                    raise_warning = True
                    tax_rate = float_round(tax_rate, precision_digits=2)
                    tax = self.env['account.tax'].sudo().search([
                        ('amount', '=', tax_rate),
                        ('amount_type', '=', 'percent'),
                        ('type_tax_use', '=', 'sale')], limit=1)
                    if not tax:
                        tax = self.env['account.tax'].sudo().create({
                            'name': 'Tax %.2f %%' % (tax_rate),
                            'amount': tax_rate,
                            'amount_type': 'percent',
                            'type_tax_use': 'sale',
                        })
                    line.tax_id = tax
        if raise_warning:
            return {'warning': _('The tax rates have been updated, you may want to check it before validation')}
        else:
            return True
