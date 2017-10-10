# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ebay_dev_id = fields.Char("Developer Key")
    ebay_sandbox_token = fields.Text("Sandbox Token")
    ebay_sandbox_app_id = fields.Char("Sandbox App Key")
    ebay_sandbox_cert_id = fields.Char("Sandbox Cert Key")

    ebay_prod_token = fields.Text("Production Token")
    ebay_prod_app_id = fields.Char("Production App Key")
    ebay_prod_cert_id = fields.Char("Production Cert Key")
    ebay_domain = fields.Selection([
        ('prod', 'Production'),
        ('sand', 'Sandbox'),
    ], string='Mode', default='sand', required=True)
    ebay_currency = fields.Many2one("res.currency", string='Currency',
                                    domain=[('ebay_available', '=', True)], required=True)
    ebay_country = fields.Many2one("res.country", domain=[('ebay_available', '=', True)],
                                   string="Country")
    ebay_site = fields.Many2one("ebay.site", string="eBay Website")
    ebay_zip_code = fields.Char(string="Zip")
    ebay_location = fields.Char(string="Location")
    ebay_out_of_stock = fields.Boolean("Out Of Stock", default=False)
    ebay_sales_team = fields.Many2one("crm.team", string="Sales Channel")
    ebay_gallery_plus = fields.Boolean("Gallery Plus", default=False)

    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param

        ebay_dev_id = self.ebay_dev_id or ''
        sandbox_token = self.ebay_sandbox_token or ''
        sandbox_app_id = self.ebay_sandbox_app_id or ''
        sandbox_cert_id = self.ebay_sandbox_cert_id or ''
        prod_token = self.ebay_prod_token or ''
        prod_app_id = self.ebay_prod_app_id or ''
        prod_cert_id = self.ebay_prod_cert_id or ''

        set_param('ebay_dev_id', ebay_dev_id)
        set_param('ebay_sandbox_token', sandbox_token)
        set_param('ebay_sandbox_app_id', sandbox_app_id)
        set_param('ebay_sandbox_cert_id', sandbox_cert_id)
        set_param('ebay_prod_token', prod_token)
        set_param('ebay_prod_app_id', prod_app_id)
        set_param('ebay_prod_cert_id', prod_cert_id)

        ebay_sales_team = self.ebay_sales_team or self.env['crm.team'].search([('team_type', '=', 'ebay')])[0]
        domain = self.ebay_domain or ''
        currency = self.ebay_currency or self.env['res.currency'].search([('ebay_available', '=', True)])[0]
        # by default all currencies active field is set to False except EUR and USD
        self.ebay_currency.active = True
        country = self.ebay_country or self.env['res.country'].search([('ebay_available', '=', True)])[0]
        site = self.ebay_site or self.env['ebay.site'].search([])[0]
        zip_code = self.ebay_zip_code or ''
        location = self.ebay_location or ''
        gallery_plus = self.ebay_gallery_plus or ''

        set_param('ebay_sales_team', ebay_sales_team.id)
        set_param('ebay_domain', domain)
        set_param('ebay_currency', currency.id)
        set_param('ebay_country', country.id)
        set_param('ebay_site', site.id)
        set_param('ebay_zip_code', zip_code)
        set_param('ebay_location', location)
        set_param('ebay_gallery_plus', gallery_plus)

        out_of_stock = self.ebay_out_of_stock or ''
        if out_of_stock != self.env['ir.config_parameter'].get_param('ebay_out_of_stock'):
            set_param('ebay_out_of_stock', out_of_stock)

            if domain == 'sand':
                if sandbox_token and sandbox_cert_id and sandbox_app_id:
                    ebay_api = Trading(
                        domain='api.sandbox.ebay.com',
                        config_file=None,
                        appid=sandbox_app_id,
                        devid="ed74122e-6f71-4877-83d8-e0e2585bd78f",
                        certid=sandbox_cert_id,
                        token=sandbox_token,
                        siteid=site.ebay_id if site else 0)
                    call_data = {
                        'OutOfStockControlPreference': 'true' if out_of_stock else 'false',
                    }
                    try:
                        ebay_api.execute('SetUserPreferences', call_data)
                    except ConnectionError:
                        pass
            else:
                if prod_token and prod_cert_id and prod_app_id:
                    ebay_api = Trading(
                        domain='api.ebay.com',
                        config_file=None,
                        appid=prod_app_id,
                        devid="ed74122e-6f71-4877-83d8-e0e2585bd78f",
                        certid=prod_cert_id,
                        token=prod_token,
                        siteid=site.ebay_id if site else 0)
                    call_data = {
                        'OutOfStockControlPreference': 'true' if out_of_stock else 'false',
                    }
                    try:
                        ebay_api.execute('SetUserPreferences', call_data)
                    except ConnectionError:
                        pass

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(
            ebay_dev_id=get_param('ebay_dev_id', default=''),
            ebay_sandbox_token=get_param('ebay_sandbox_token', default=''),
            ebay_sandbox_app_id=get_param('ebay_sandbox_app_id', default=''),
            ebay_sandbox_cert_id=get_param('ebay_sandbox_cert_id', default=''),
            ebay_prod_token=get_param('ebay_prod_token', default=''),
            ebay_prod_app_id=get_param('ebay_prod_app_id', default=''),
            ebay_prod_cert_id=get_param('ebay_prod_cert_id', default=''),
            ebay_domain=get_param('ebay_domain', default='sand'),
            ebay_currency=int(get_param('ebay_currency', default=self.env.ref('base.USD'))),
            ebay_country=int(get_param('ebay_country', default=self.env.ref('base.us'))),
            ebay_site=int(get_param('ebay_site', default=self.env['ebay.site'].search([])[0])),
            ebay_zip_code=get_param('ebay_zip_code'),
            ebay_location=get_param('ebay_location'),
            ebay_out_of_stock=get_param('ebay_out_of_stock', default=False),
            ebay_sales_team=int(get_param('ebay_sales_team', default=self.env['crm.team'].search([('team_type', '=', 'ebay')], limit=1))),
            ebay_gallery_plus=get_param('ebay_gallery_plus'),
        )
        return res

    @api.model
    def button_sync_categories(self, context=None):
        self.env['ebay.category']._cron_sync()

    @api.model
    def button_sync_product_status(self, context=None):
        self.env['product.template'].sync_product_status()

    @api.model
    def sync_policies(self, context=None):
        self.env['ebay.policy'].sync_policies()

    @api.model
    def sync_ebay_details(self, context=None):
        response = self.env['product.template'].ebay_execute(
            'GeteBayDetails',
            {'DetailName': ['CountryDetails', 'SiteDetails', 'CurrencyDetails']}
        )
        for country in self.env['res.country'].search([('ebay_available', '=', True)]):
            country.ebay_available = False
        for country in response.dict()['CountryDetails']:
            record = self.env['res.country'].search([('code', '=', country['Country'])])
            if record:
                record.ebay_available = True
        for currency in self.env['res.currency'].search([('ebay_available', '=', True)]):
            currency.ebay_available = False
        for currency in response.dict()['CurrencyDetails']:
            record = self.env['res.currency'].with_context(active_test=False).search([('name', '=', currency['Currency'])])
            if record:
                record.ebay_available = True
        for site in response.dict()['SiteDetails']:
            record = self.env['ebay.site'].search([('ebay_id', '=', site['SiteID'])])
            if not record:
                record = self.env['ebay.site'].create({
                    'name': site['Site'],
                    'ebay_id': site['SiteID']
                })
            else:
                record.name = site['Site']
