# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rules_company_id = fields.Many2one('res.company', string='Select Company',
        help='Select company to setup Inter company rules.')
    rule_type = fields.Selection([('so_and_po', 'Send Sales & Purchase Orders'),
        ('invoice_and_refunds', 'Send Invoices & Credit Notes')],
        help='Select the type to setup inter company rules in selected company.')
    so_from_po = fields.Boolean(string='Create Sales Orders when buying to this company',
        help='Generate a Sale Order when a Purchase Order with this company as vendor is created.')
    po_from_so = fields.Boolean(string='Create Purchase Orders when selling to this company',
        help='Generate a Purchase Order when a Sale Order with this company as customer is created.')
    auto_validation = fields.Boolean(string='Auto-validate Sales/Purchase Orders',
        help='''When a Sale Order or a Purchase Order is created by a multi
            company rule for this company, it will automatically validate it.''')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse For Purchase Orders',
        help='Default value to set on Purchase Orders that will be created based on Sales Orders made to this company.')

    @api.onchange('rule_type')
    def onchange_rule_type(self):
        if self.rule_type == 'so_and_po':
            self.invoice_and_refunds = False

    @api.onchange('rules_company_id')
    def onchange_rules_company_id(self):
        if self.rules_company_id:
            rule_type = False
            if self.rules_company_id.so_from_po or self.rules_company_id.po_from_so or self.rules_company_id.auto_validation:
                rule_type = 'so_and_po'
            elif self.rules_company_id.auto_generate_invoices:
                rule_type = 'invoice_and_refunds'

            self.rule_type = rule_type
            self.so_from_po = self.rules_company_id.so_from_po
            self.po_from_so = self.rules_company_id.po_from_so
            self.auto_validation = self.rules_company_id.auto_validation
            self.warehouse_id = self.rules_company_id.warehouse_id.id

    # YTI FIXME: Could define related fields instead
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        if self.rules_company_id:
            vals = {
                'so_from_po': self.so_from_po if self.rule_type == 'so_and_po' else False,
                'po_from_so': self.po_from_so if self.rule_type == 'so_and_po' else False,
                'auto_validation': self.auto_validation if self.rule_type == 'so_and_po' else False,
                'auto_generate_invoices': True if self.rule_type == 'invoice_and_refunds' else False,
                'warehouse_id': self.warehouse_id.id
            }
            self.rules_company_id.write(vals)
