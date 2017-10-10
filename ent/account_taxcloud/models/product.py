# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductTicCategory(models.Model):
    _name = 'product.tic.category'
    _descrition = "TaxCloud Taxabilty information code for Product Category."
    _rec_name = 'code'

    code = fields.Integer(string="TIC Category Code", required=True)
    description = fields.Char(string='TIC Description', required=True)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('description', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        return recs.name_get()

    @api.multi
    def name_get(self):
        res = []
        for category in self:
            res.append((category.id, _('[%s] %s') % (category.code, category.description[0:50])))
        return res

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    tic_category_id = fields.Many2one('product.tic.category', string="TaxCloud Category",
        help="TaxCloud uses Taxability Information Codes (TIC) to make sure each item in your catalog "
             "is taxed at the right rate (or, for tax-exempt items, not taxed at all), so it's important "
             "to make sure that each item is assigned a TIC. If you can't find the right tax category for "
             "an item in your catalog, you can assign it to the 'General Goods and Services' TIC, 00000. "
             "TaxCloud automatically assigns products to this TIC as a default, so unless you've changed an "
             "item's TIC in the past, it should already be set to 00000.")

class ResCompany(models.Model):
    _inherit = 'res.company'

    tic_category_id = fields.Many2one('product.tic.category', string='Default TIC Code', help="Default TICs(Taxability information codes) code to get sales tax from TaxCloud by product category.")
