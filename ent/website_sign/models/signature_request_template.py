# -*- coding: utf-8 -*-
import re
import uuid

from odoo import api, fields, models, _
from odoo.tools import pycompat


class SignatureRequestTemplate(models.Model):
    _name = "signature.request.template"
    _description = "Signature Request Template"
    _rec_name = "attachment_id"

    attachment_id = fields.Many2one('ir.attachment', string="Attachment", required=True, ondelete='cascade')
    signature_item_ids = fields.One2many('signature.item', 'template_id', string="Signature Items")

    archived = fields.Boolean(default=False, string="Archived")
    favorited_ids = fields.Many2many('res.users', string="Favorite of")

    share_link = fields.Char(string="Share Link")

    signature_request_ids = fields.One2many('signature.request', 'template_id', string="Signature Requests")

    color = fields.Integer()

    @api.multi
    def go_to_custom_template(self):
        self.ensure_one()
        return {
            'name': "Template \"%(name)s\"" % {'name': self.attachment_id.name},
            'type': 'ir.actions.client',
            'tag': 'website_sign.Template',
            'context': {
                'id': self.id,
            },
        }
        
    @api.multi
    def toggle_archived(self):
        self.ensure_one()
        self.archived = not self.archived

    @api.multi
    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self[0].favorited_ids else 4, self.env.user.id)]})

    @api.model
    def upload_template(self, name=None, dataURL=None):
        mimetype = dataURL[dataURL.find(':')+1:dataURL.find(',')]
        datas = dataURL[dataURL.find(',')+1:]
        attachment = self.env['ir.attachment'].create({'name': name[:name.rfind('.')], 'datas_fname': name, 'datas': datas, 'mimetype': mimetype})
        template = self.create({'attachment_id': attachment.id, 'favorited_ids': [(4, self.env.user.id)]})
        return {'template': template.id, 'attachment': attachment.id}

    @api.model
    def update_from_pdfviewer(self, template_id=None, duplicate=None, signature_items=None, name=None):
        template = self.browse(template_id)
        if not duplicate and len(template.signature_request_ids) > 0:
            return False

        if duplicate:
            new_attachment = template.attachment_id.copy()
            r = re.compile(' \(v(\d+)\)$')
            m = r.search(name)
            v = str(int(m.group(1))+1) if m else "2"
            index = m.start() if m else len(name)
            new_attachment.name = name[:index] + " (v" + v + ")"

            template = self.create({
                'attachment_id': new_attachment.id,
                'favorited_ids': [(4, self.env.user.id)]
            })
        elif name:
            template.attachment_id.name = name

        item_ids = {
            it
            for it in pycompat.imap(int, signature_items)
            if it > 0
        }
        template.signature_item_ids.filtered(lambda r: r.id not in item_ids).unlink()
        for item in template.signature_item_ids:
            item.write(signature_items.pop(str(item.id)))
        SignatureItem = self.env['signature.item']
        for item in signature_items.values():
            item['template_id'] = template.id
            SignatureItem.create(item)

        if len(template.signature_item_ids.mapped('responsible_id')) > 1:
            template.share_link = None
        return template.id

    @api.model
    def share(self, id, **post):
        template = self.browse(id)
        if len(template.signature_item_ids.mapped('responsible_id')) > 1:
            return False

        if not template.share_link:
            template.share_link = str(uuid.uuid4())
        return template.share_link

class SignatureItem(models.Model):
    _name = "signature.item"
    _description = "Signature Field For Document To Sign"

    template_id = fields.Many2one('signature.request.template', string="Document Template", required=True, ondelete='cascade')

    type_id = fields.Many2one('signature.item.type', string="Type", required=True, ondelete='cascade')

    required = fields.Boolean(default=True)
    responsible_id = fields.Many2one("signature.item.party", string="Responsible")

    name = fields.Char(string="Field Name")
    page = fields.Integer(string="Document Page", required=True, default=1)
    posX = fields.Float(digits=(4, 3), string="Position X", required=True)
    posY = fields.Float(digits=(4, 3), string="Position Y", required=True)
    width = fields.Float(digits=(4, 3), required=True)
    height = fields.Float(digits=(4, 3), required=True)

    @api.multi
    def getByPage(self):
        items = {}
        for item in self:
            if item.page not in items:
                items[item.page] = []
            items[item.page].append(item)
        return items

class SignatureItemType(models.Model):
    _name = "signature.item.type"
    _description = "Specialized type for signature fields"

    name = fields.Char(string="Field Name", required=True, translate=True)
    type = fields.Selection([
        ('signature', "Signature"),
        ('initial', "Initial"),
        ('text', "Text"),
        ('textarea', "Multiline Text"),
    ], required=True, default='text')

    tip = fields.Char(required=True, default="fill in")
    placeholder = fields.Char()

    default_width = fields.Float(string="Default Width", digits=(4, 3), required=True, default=0.150)
    default_height = fields.Float(string="Default Height", digits=(4, 3), required=True, default=0.015)
    auto_field = fields.Char(string="Automatic Partner Field", help="Partner field to use to auto-complete the fields of this type")

class SignatureItemValue(models.Model):
    _name = "signature.item.value"
    _description = "Signature Field Value For Document To Sign"

    signature_item_id = fields.Many2one('signature.item', string="Signature Item", required=True, ondelete='cascade')
    signature_request_id = fields.Many2one('signature.request', string="Signature Request", required=True, ondelete='cascade')

    value = fields.Text()

class SignatureItemParty(models.Model):
    _name = "signature.item.party"
    _description = "Type of partner which can access a particular signature field"

    name = fields.Char(required=True, translate=True)

    @api.model
    def add(self, name):
        party = self.search([('name', '=', name)])
        return party.id if party else self.create({'name': name}).id
