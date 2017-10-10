# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .taxcloud_request import TaxCloudRequest


class AccountFiscalPositionTemplate(models.Model):
    _inherit = 'account.fiscal.position.template'

    is_taxcloud = fields.Boolean(string='Use TaxCloud API')


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    is_taxcloud = fields.Boolean(string='Use TaxCloud API')

    @api.multi
    def map_tax(self, taxes, product=None, partner=None):

        if not taxes or not self.is_taxcloud or partner is None:
            return super(AccountFiscalPosition, self).map_tax(taxes)

        AccountTax = self.env['account.tax'].sudo()
        result = AccountTax.browse()

        tic_category = self.env['product.tic.category']
        if partner:
            tic_category = product.tic_category_id
            if not tic_category:
                tic_category = self.company_id.tic_category_id or self.env.user.company_id.tic_category_id

        for tax in taxes:

            # step 1: Check on the fiscal position if a tax mapping is already existing with the same
            # Tic Category, State, Tax value and ZIP code. If not, fetch taxcloud.
            tax_line = self.tax_ids.filtered(lambda x:
                tic_category.id in x.tic_category_ids.ids and
                partner.state_id.id in x.state_ids.ids and
                x.tax_src_id.id == tax.id and
                x.tax_dest_id and
                partner.zip in x.zip_codes.split(','))
            if not tax_line:
                res = self.get_tax_from_taxcloud(partner, tic_category.code, product.id)

                # step 2: Check tax of that percentage already exists.
                taxcloud_tax = AccountTax.search([
                    ('amount', '=', res.get('tax_amount')),
                    ('amount_type', '=', 'percent'),
                    ('type_tax_use', '=', 'sale')], limit=1)
                if not taxcloud_tax:
                    taxcloud_tax = AccountTax.create({
                        'name': 'Tax %s %%' % (res.get('tax_amount')),
                        'amount': res.get('tax_amount'),
                        'amount_type': 'percent',
                        'type_tax_use': 'sale',
                        'account_id': tax.account_id.id,
                        'refund_account_id': tax.refund_account_id.id
                    })

                # step 3: If source and destination tax already exist in mapping
                # line just write category, state and zip on that mapping line.
                tax_line = self.tax_ids.filtered(lambda x: x.tax_src_id.id == tax.id and x.tax_dest_id.id == taxcloud_tax.id)
                if not tax_line:
                    tax_line = self.env['account.fiscal.position.tax'].sudo().create({
                        'position_id': self.id,
                        'tax_src_id': tax.id,
                        'tax_dest_id': taxcloud_tax.id,
                        'tic_category_ids': [(6, 0, [tic_category.id])] if tic_category else False,
                        'state_ids': [(6, 0, [partner.state_id.id])] if partner.state_id else False,
                        'zip_codes': partner.zip
                    })
                if tic_category and tic_category.id not in tax_line.tic_category_ids.ids:
                    tax_line.sudo().write({'tic_category_ids': [(4, tic_category.id)]})
                if partner.state_id and partner.state_id.id not in tax_line.state_ids.ids:
                    tax_line.sudo().write({'state_ids': [(4, partner.state_id.id)]})
                if partner.zip and partner.zip not in tax_line.zip_codes.split(','):
                    tax_line.sudo().write({'zip_codes': "%s,%s" % (tax_line.zip_codes, partner.zip)})
            result |= tax_line.tax_dest_id
        return result

    # Get tax from TaxCloud API
    def get_tax_from_taxcloud(self, recipient_partner, tic_code, product_id=1):
        Param = self.env['ir.config_parameter'].sudo()
        api_id = Param.get_param('account_taxcloud.taxcloud_api_id')
        api_key = Param.get_param('account_taxcloud.taxcloud_api_key')
        request = TaxCloudRequest(api_id, api_key)

        shipper = self.company_id or self.env.user.company_id
        request.set_location_origin_detail(shipper)
        request.set_location_destination_detail(recipient_partner)

        request.set_items_detail(product_id, tic_code)

        res = request.get_tax()
        if res.get('error_message'):
            raise ValidationError(_('Unable to retrieve taxes from TaxCloud: ')+'\n'+res['error_message']+'\n\n'+_('The configuration of TaxCloud is in the Accounting app, Settings menu.'))
        return res


class AccountFiscalPositionTaxTemplate(models.Model):
    _inherit = 'account.fiscal.position.tax.template'

    tic_category_ids = fields.Many2many('product.tic.category', string="TIC Category")
    state_ids = fields.Many2many('res.country.state', string="Federal States")
    zip_codes = fields.Char("Zip")


class AccountFiscalPositionTax(models.Model):
    _inherit = 'account.fiscal.position.tax'

    tic_category_ids = fields.Many2many('product.tic.category', string="TIC Category")
    state_ids = fields.Many2many('res.country.state', string="Federal States")
    zip_codes = fields.Char("Zip")
