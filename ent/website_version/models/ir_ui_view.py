# -*- coding: utf-8 -*-
from lxml import etree
from odoo import tools, fields, models, api
from odoo.tools import pycompat


class Qweb(models.AbstractModel):

    _inherit = "ir.qweb"

    def _read_template_keys(self):
        return super(view, self)._read_template_keys() + ['website_id', 'version_id']


class view(models.Model):

    _inherit = "ir.ui.view"

    version_id = fields.Many2one('website_version.version', ondelete='cascade', string="Version")

    def _sort_suitability_key(self):
        """
        Key function to sort views by descending suitability

        Suitability of a view is defined as follow:

        * if the view and request version are matched,
        * then fallback on previously defined suitability
        """
        original_suitability = super(view, self)._sort_suitability_key()

        context_version_id = self.env.context.get('version_id', 0)
        different_version = context_version_id != (self.version_id.id or 0)

        return (different_version, original_suitability)

    @api.multi
    def write(self, vals):
        if self.env.context is None:
            self.env.context = {}

        version_id = self.env.context.get('version_id')
        #If you write on a shared view, your modifications will be seen on every website wich uses these view.
        #To dedicate a view for a specific website, you must create a version and publish these version.
        if version_id and not self.env.context.get('write_on_view') and not 'active' in vals:
            self.env.context = dict(self.env.context, write_on_view=True)
            version = self.env['website_version.version'].browse(version_id)
            website_id = version.website_id.id
            version_view_ids = self.env['ir.ui.view']
            for current in self:
                #check if current is in version
                if current.version_id.id == version_id:
                    version_view_ids += current
                else:
                    new_v = self.search([('website_id', '=', website_id), ('version_id', '=', version_id), ('key', '=', current.key)])
                    if new_v:
                        version_view_ids += new_v
                    else:
                        copy_v = current.copy({'version_id': version_id, 'website_id': website_id})
                        version_view_ids += copy_v
            return super(view, version_view_ids).write(vals)
        else:
            self.env.context = dict(self.env.context, write_on_view=True)
            return super(view, self).write(vals)

    @api.one
    def publish(self):
        #To delete and replace views which are in the website( in fact with website_id)
        master_record = self.search([('key', '=', self.key), ('version_id', '=', False), ('website_id', '=', self.website_id.id)])
        if master_record:
            master_record.unlink()
        self.copy({'version_id': None})

    #To publish a view in backend
    @api.multi
    def action_publish(self):
        self.publish()

    @api.model
    def get_view_id(self, xml_id):
        if self.env.context and 'website_id' in self.env.context and not isinstance(xml_id, pycompat.integer_types):
            domain = [('key', '=', xml_id), '|', ('website_id', '=', self.env.context['website_id']), ('website_id', '=', False)]
            if 'version_id' in self.env.context:
                domain += ['|', ('version_id', '=', self.env.context['version_id']), ('version_id', '=', False)]
            xml_id = self.search(domain, order='website_id,version_id', limit=1).id
        else:
            xml_id = super(view, self).get_view_id(xml_id)
        return xml_id

    #To take the right inheriting views
    @api.model
    def get_inheriting_views_arch(self, view_id, model):
        arch = super(view, self).get_inheriting_views_arch(view_id, model)
        vw = self.browse(view_id)
        if not (self.env.context and self.env.context.get('website_id') and vw.type == 'qweb'):
            return arch

        # keep the most suited view when several view with same key are available
        chosen_view_ids = self.browse(view_id for _, view_id in arch).filter_duplicate().ids

        return [x for x in arch if x[1] in chosen_view_ids]

    #To active or desactive the right views according to the key
    @api.multi
    def toggle(self):
        """ Switches between enabled and disabled statuses
        """
        ctx = self.env.context.copy()
        ctx['active_test'] = False

        for view in self:
            all_records = self.with_context(ctx).search([('key', '=', view.key)])
            for v in all_records:
                v.write({'active': not v.active})
