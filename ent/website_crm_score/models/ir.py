# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.http import request
from odoo.osv import osv


class ir_http(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _serve_page(cls):
        response = super(ir_http, cls)._serve_page()

        if response and getattr(response, 'status_code', 0) == 200:
            if response.qcontext.get('main_object', request.env['ir.ui.view']).track:  # avoid tracking redirected page
                lead_id = request.env["crm.lead"].decode(request)
                url = request.httprequest.url
                vals = {'lead_id': lead_id, 'user_id': request.session.get('uid'), 'url': url}

                if not lead_id or request.env['website.crm.pageview'].create_pageview(vals):
                    # create_pageview failed
                    response.delete_cookie('lead_id')
                    request.session.setdefault('pages_viewed', {})[url] = fields.Datetime.now()
                    request.session.modified = True

        return response


    @classmethod
    def _dispatch(cls):
        delete_cookie = False

        if request.endpoint and request.endpoint.routing and request.endpoint.routing.get('track'):
            lead_id = request.env["crm.lead"].decode(request)
            url = request.httprequest.url
            vals = {'lead_id': lead_id, 'user_id': request.session.get('uid'), 'url': url}
            if not lead_id or request.env['website.crm.pageview'].create_pageview(vals):
                # create_pageview was fail
                delete_cookie = True
                request.session.setdefault('pages_viewed', {})[url] = fields.Datetime.now()
                request.session.modified = True

        response = super(ir_http, cls)._dispatch()
        if isinstance(response, Exception):
            return response

        if delete_cookie:
            response.delete_cookie('lead_id')

        return response


class view(osv.osv):
    _inherit = "ir.ui.view"

    track = fields.Boolean(string='Track', default=False, help="Allow to specify for one page of the website to be trackable or not")
