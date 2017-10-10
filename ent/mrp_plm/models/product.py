# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    version = fields.Integer('Version', default=1)
    eco_count = fields.Integer('# ECOs',compute='_compute_eco_count')
    eco_ids = fields.One2many('mrp.eco', 'product_tmpl_id', 'ECOs')
    template_attachment_count = fields.Integer('# Attachments', compute='_compute_attachments')

    @api.multi
    def _compute_eco_count(self):
        for p in self:
            p.eco_count = len(p.eco_ids)

    @api.multi
    def _compute_attachments(self):
        for p in self:
            attachments = self.env['mrp.document'].search(['&', ('res_model', '=', 'product.template'), ('res_id', '=', p.id)])
            p.template_attachment_count = len(attachments)

    @api.multi
    def action_see_attachments(self):
        domain = ['&', ('res_model', '=', 'product.template'), ('res_id', '=', self.id)]
        attachment_view = self.env.ref('mrp.view_document_file_kanban_mrp')
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'mrp.document',
            'type': 'ir.actions.act_window',
            'view_id': attachment_view.id,
            'views': [(attachment_view.id, 'kanban'), (False, 'form')],
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''<p class="oe_view_nocontent_create">
                        Click to upload files to your product.
                    </p><p>
                        Use this feature to store any files, like drawings or specifications.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % ('product.template', self.id)
        }
