# -*- coding: utf-8 -*-
import base64
import mimetypes
import os
import re

from odoo import http, _
from odoo.addons.web.controllers.main import content_disposition

class WebsiteSign(http.Controller):

    def get_document_qweb_context(self, id, token):
        signature_request = http.request.env['signature.request'].sudo().search([('id', '=', id)])
        if not signature_request:
            if token:
                return http.request.render('website_sign.deleted_sign_request')
            else:
                return http.request.not_found()

        current_request_item = None
        if token:
            current_request_item = signature_request.request_item_ids.filtered(lambda r: r.access_token == token)
            if not current_request_item and signature_request.access_token != token and http.request.env.user.id != signature_request.create_uid.id:
                return http.request.render('website_sign.deleted_sign_request')
        elif signature_request.create_uid.id != http.request.env.user.id:
            return http.request.not_found()

        signature_item_types = http.request.env['signature.item.type'].search_read([])
        if current_request_item:
            for item_type in signature_item_types:
                if item_type['auto_field']:
                    fields = item_type['auto_field'].split('.')
                    auto_field = current_request_item.partner_id
                    for field in fields:
                        if auto_field and field in auto_field:
                            auto_field = auto_field[field]
                        else:
                            auto_field = ""
                            break
                    item_type['auto_field'] = auto_field

        sr_values = http.request.env['signature.item.value'].sudo().search([('signature_request_id', '=', signature_request.id)])
        item_values = {}
        for value in sr_values:
            item_values[value.signature_item_id.id] = value.value

        return {
            'signature_request': signature_request,
            'current_request_item': current_request_item,
            'token': token,
            'nbComments': len(signature_request.message_ids.filtered(lambda m: m.message_type == 'comment')),
            'isPDF': (signature_request.template_id.attachment_id.mimetype.find('pdf') > -1),
            'webimage': re.match('image.*(gif|jpe|jpg|png)', signature_request.template_id.attachment_id.mimetype),
            'hasItems': len(signature_request.template_id.signature_item_ids) > 0,
            'signature_items': signature_request.template_id.signature_item_ids,
            'item_values': item_values,
            'role': current_request_item.role_id.id if current_request_item else 0,
            'readonly': not (current_request_item and current_request_item.state == 'sent'),
            'signature_item_types': signature_item_types,
        }

    # -------------
    #  HTTP Routes
    # -------------
    @http.route(["/sign/document/<int:id>"], type='http', auth='user')
    def sign_document_user(self, id, **post):
        return self.sign_document_public(id, None)

    @http.route(["/sign/document/<int:id>/<token>"], type='http', auth='public')
    def sign_document_public(self, id, token, **post):
        document_context = self.get_document_qweb_context(id, token)
        if not isinstance(document_context, dict):
            return document_context

        return http.request.render('website_sign.doc_sign', document_context)

    @http.route(['/sign/download/<int:id>/<token>/<type>'], type='http', auth='public')
    def download_document(self, id, token, type, **post):
        signature_request = http.request.env['signature.request'].sudo().search([('id', '=', id), ('access_token', '=', token)])
        if not signature_request:
            return http.request.not_found()

        document = None
        if type == "origin":
            document = signature_request.template_id.attachment_id.datas
        elif type == "completed":
            document = signature_request.completed_document

        if not document:
            return http.redirect_with_hash("/sign/document/%(request_id)s/%(access_token)s" % {'request_id': id, 'access_token': token})

        filename = signature_request.reference
        if filename != signature_request.template_id.attachment_id.datas_fname:
            filename += signature_request.template_id.attachment_id.datas_fname[signature_request.template_id.attachment_id.datas_fname.rfind('.'):]

        return http.request.make_response(
            base64.b64decode(document),
            headers = [
                ('Content-Type', mimetypes.guess_type(filename)[0] or 'application/octet-stream'),
                ('Content-Disposition', content_disposition(filename))
            ]
        )

    @http.route(['/sign/<link>'], type='http', auth='public')
    def share_link(self, link, **post):
        template = http.request.env['signature.request.template'].sudo().search([('share_link', '=', link)], limit=1)
        if not template:
            return http.request.not_found()

        signature_request = http.request.env['signature.request'].sudo().create({
            'template_id': template.id,
            'reference': "%(template_name)s-public" % {'template_name': template.attachment_id.name}
        })

        request_item = http.request.env['signature.request.item'].sudo().create({'signature_request_id': signature_request.id, 'role_id': template.signature_item_ids.mapped('responsible_id').id})
        signature_request.action_sent()

        return http.redirect_with_hash('/sign/document/%(request_id)s/%(access_token)s' % {'request_id': signature_request.id, 'access_token': request_item.access_token})

    # -------------
    #  JSON Routes
    # -------------
    @http.route(["/sign/get_document/<int:id>/<token>"], type='json', auth='user')
    def get_document(self, id, token):
        return http.Response(template='website_sign._doc_sign', qcontext=self.get_document_qweb_context(id, token)).render()

    @http.route(['/sign/get_fonts'], type='json', auth='public')
    def get_fonts(self):
        fonts_directory = os.path.dirname(os.path.abspath(__file__)) + '/../static/font'
        font_filenames = sorted(os.listdir(fonts_directory))

        fonts = []
        for filename in font_filenames:
            font_file = open(fonts_directory + '/' + filename, 'r')
            font = base64.b64encode(font_file.read())
            fonts.append(font)
        return fonts

    @http.route(['/sign/new_partners'], type='json', auth='user')
    def new_partners(self, partners=[]):
        ResPartner = http.request.env['res.partner']
        pIDs = []
        for p in partners:
            existing = ResPartner.search([('email', '=', p[1])], limit=1)
            pIDs.append(existing.id if existing else ResPartner.create({'name': p[0], 'email': p[1]}).id)
        return pIDs

    @http.route(['/sign/send_public/<int:id>/<token>'], type='json', auth='public')
    def make_public_user(self, id, token, name=None, mail=None):
        signature_request = http.request.env['signature.request'].sudo().search([('id', '=', id), ('access_token', '=', token)])
        if not signature_request or len(signature_request.request_item_ids) != 1 or signature_request.request_item_ids.partner_id:
            return False

        ResPartner = http.request.env['res.partner'].sudo()
        partner = ResPartner.search([('email', '=', mail)], limit=1)
        if not partner:
            partner = ResPartner.create({'name': name, 'email': mail})
        signature_request.request_item_ids[0].write({'partner_id': partner.id})

    @http.route(['/sign/sign/<int:id>/<token>'], type='json', auth='public')
    def sign(self, id, token, signature=None):
        request_item = http.request.env['signature.request.item'].sudo().search([('signature_request_id', '=', id), ('access_token', '=', token), ('state', '=', 'sent')], limit=1)
        if not (request_item and request_item.sign(signature)):
            return False

        request_item.action_completed()
        request = request_item.signature_request_id
        request._message_post(_('Signed.'), request_item.partner_id, type='comment', subtype='mt_comment')
        if request.state == 'signed':
            request._message_post(_('Everybody Signed.'), type='comment', subtype='mt_comment')
        return True

    @http.route(['/sign/get_notes/<int:id>/<token>'], type='json', auth='public')
    def get_notes(self, id, token):
        request = http.request.env['signature.request'].sudo().search([('id', '=', id), ('access_token', '=', token)], limit=1)
        if not request:
            return []

        DateTimeConverter = http.request.env['ir.qweb.field.datetime']
        ResPartner = http.request.env['res.partner'].sudo()
        messages = request.message_ids.read(['message_type', 'author_id', 'date', 'body'])
        for m in messages:
            author_id = m['author_id'][0]
            author = ResPartner.browse(author_id)
            m['author_id'] = author.read(['name'])[0]
            m['author_id']['avatar'] = '/web/image/res.partner/%s/image_small' % author_id
            m['date'] = DateTimeConverter.value_to_html(m['date'], '')
        return messages

    @http.route(['/sign/send_note/<int:id>/<token>'], type='json', auth='public')
    def send_note(self, id, token, access_token=None, message=None):
        request = http.request.env['signature.request'].sudo().search([('id', '=', id), ('access_token', '=', token)], limit=1)
        if not request:
            return

        request_item = request.request_item_ids.filtered(lambda r: r.access_token == access_token)
        partner = request_item.partner_id if request_item else None
        if (partner or http.request.env.user.id == request.create_uid.id) and message:
            request._message_post(message, partner, type='comment', subtype='mt_comment')

    @http.route(['/sign/save_location/<int:id>/<token>'], type='json', auth='public')
    def save_location(self, id, token, latitude=0, longitude=0):
        signature_request_item = http.request.env['signature.request.item'].sudo().search([('signature_request_id', '=', id), ('access_token', '=', token)], limit=1)
        signature_request_item.write({'latitude': latitude, 'longitude': longitude})
