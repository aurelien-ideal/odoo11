# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .taxcloud_request import TaxCloudRequest

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    taxcloud_api_id = fields.Char(string='TaxCloud API ID')
    taxcloud_api_key = fields.Char(string='TaxCloud API KEY')
    tic_category_id = fields.Many2one(related='company_id.tic_category_id', string="Default TIC Code")

    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param("account_taxcloud.taxcloud_api_id", (self.taxcloud_api_id or '').strip())
        Param.set_param("account_taxcloud.taxcloud_api_key", (self.taxcloud_api_key or '').strip())

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            taxcloud_api_id=params.get_param('account_taxcloud.taxcloud_api_id', default=''),
            taxcloud_api_key=params.get_param('account_taxcloud.taxcloud_api_key', default=''),
        )
        return res

    @api.multi
    def sync_taxcloud_category(self):
        Category = self.env['product.tic.category']
        request = TaxCloudRequest(self.taxcloud_api_id, self.taxcloud_api_key)
        res = request.get_tic_category()

        if res.get('error_message'):
            raise ValidationError(_('Unable to retrieve taxes from TaxCloud: ')+'\n'+res['error_message']+'\n\n'+_('The configuration of TaxCloud is in the Accounting app, Settings menu.'))

        for category in res['data']:
            if not Category.search([('code', '=', category['TICID'])], limit=1):
                Category.create({'code': category['TICID'], 'description': category['Description']})
        if not self.env.user.company_id.tic_category_id:
            self.env.user.company_id.tic_category_id = Category.search([('code', '=', 0)], limit=1)
        return True
