# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.addons.http_routing.models.ir_http import slugify

class PageVersion(models.Model):
    _inherit = "website.page"

    @api.model
    def save_page_info(self, website_id, data):
        """ With website_version enabled, a page's version is a ir.ui.view with
            the same key but with a version_id set.
            This is why we should modify the key of every page that is a version
            of the page we are modifying or theses versions just wont be
            recognized as such anymore.
        """
        page = self.browse(int(data['id']))
        pages = self.env['ir.ui.view'].search([
            ('key', '=', page.key),
            '|', ('website_id', '=', False), ('website_id', '=', website_id)
        ])
        pages.write({'key': 'website.' + slugify(data['name'], 50), 'name': data['name']})

        return super(PageVersion, self).save_page_info(website_id, data)

    @api.multi
    def unlink(self):
        """ When a website_page is deleted, the ORM does not delete its ir_ui_view.
            The page's ir.ui.view is deleted in website.page unlink override.
            We should also delete ir.ui.view that are versions of the page's ir.ui.view
        """
        # Handle it's ir_ui_view
        for page in self:
            # Other pages linked to the ir_ui_view of the page being deleted (will it even be possible?)
            pages_linked_to_iruiview = self.search_count(
                [('view_id', '=', self.view_id.id), ('id', '!=', self.id)]
            )
            if not pages_linked_to_iruiview:
                # If there is no other pages linked to that ir_ui_view, we can delete its versions
                self.env['ir.ui.view'].search([
                    ('key', '=', self.key), ('id', '!=', page.view_id.id),
                    '|', ('website_id', '=', False), ('website_id', '=', self.env['website'].get_current_website().id)
                ]).unlink()
        # And then delete the website_page itself
        return super(PageVersion, self).unlink()
