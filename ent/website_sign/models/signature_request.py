# -*- coding: utf-8 -*-
import base64
import io
import time
import uuid
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class SignatureRequest(models.Model):
    _name = "signature.request"
    _description = "Document To Sign"
    _rec_name = 'reference'
    _inherit = 'mail.thread'

    @api.multi
    def _default_access_token(self):
        return str(uuid.uuid4())

    template_id = fields.Many2one('signature.request.template', string="Template", required=True)
    reference = fields.Char(required=True, string="Filename")

    access_token = fields.Char('Security Token', required=True, default=_default_access_token, readonly=True)

    request_item_ids = fields.One2many('signature.request.item', 'signature_request_id', string="Signers")
    state = fields.Selection([
        ("draft", "Draft"),
        ("sent", "Signatures in Progress"),
        ("signed", "Fully Signed"),
        ("canceled", "Canceled")
    ], default='draft', track_visibility='onchange')

    follower_ids = fields.Many2many('res.partner', string="Document Followers")

    completed_document = fields.Binary(readonly=True, string="Completed Document", attachment=True)

    nb_draft = fields.Integer(string="Draft Requests", compute="_compute_count", store=True)
    nb_wait = fields.Integer(string="Sent Requests", compute="_compute_count", store=True)
    nb_closed = fields.Integer(string="Completed Signatures", compute="_compute_count", store=True)
    progress = fields.Integer(string="Progress", compute="_compute_count")

    archived = fields.Boolean(string="Archived", default=False)
    favorited_ids = fields.Many2many('res.users', string="Favorite of")

    color = fields.Integer()
    request_item_infos = fields.Binary(compute="_compute_request_item_infos")
    last_action_date = fields.Datetime(related="message_ids.create_date", readonly=True)

    @api.one
    @api.depends('request_item_ids.state')
    def _compute_count(self):
        draft, wait, closed = 0, 0, 0
        for s in self.request_item_ids:
            if s.state == "draft":
                draft += 1
            if s.state == "sent":
                wait += 1
            if s.state == "completed":
                closed += 1
        self.nb_draft = draft
        self.nb_wait = wait
        self.nb_closed = closed

        if self.nb_wait + self.nb_closed <= 0:
            self.progress = 0
        else:
            self.progress = self.nb_closed*100 / (self.nb_wait + self.nb_closed)

    @api.one
    @api.depends('request_item_ids.state', 'request_item_ids.partner_id.name')
    def _compute_request_item_infos(self):
        infos = []
        for item in self.request_item_ids:
            infos.append({
                'partner_name': item.partner_id.name if item.partner_id else 'Public User',
                'state': item.state,
            })
        self.request_item_infos = infos

    @api.one
    def _check_after_compute(self):
        if self.state == 'draft' and self.nb_draft == 0 and len(self.request_item_ids) > 0: # When a draft partner is deleted
            self.action_sent()
        elif self.state == 'sent':
            if self.nb_draft > 0 or len(self.request_item_ids) == 0: # A draft partner is added or all partner are deleted
                self.action_draft()
            elif self.nb_closed == len(self.request_item_ids) and len(self.request_item_ids) > 0: # All signed
                self.action_signed()
        elif self.state == 'signed' and (self.nb_draft > 0 or len(self.request_item_ids) == 0): # A draft partner is added or all removed
            self.action_draft()

    @api.multi
    def button_send(self):
        self.action_sent()

    @api.multi
    def go_to_document(self):
        self.ensure_one()
        request_item = self.request_item_ids.filtered(lambda r: r.partner_id and r.partner_id.id == self.env.user.partner_id.id)
        return {
            'name': "Document \"%(name)s\"" % {'name': self.reference},
            'type': 'ir.actions.client',
            'tag': 'website_sign.Document',
            'context': {
                'id': self.id,
                'token': self.access_token,
                'sign_token': request_item.access_token if request_item and request_item.state == "sent" else None,
                'create_uid': self.create_uid.id,
                'state': self.state,
            },
        }

    @api.multi
    def get_completed_document(self):
        self.ensure_one()
        if not self.completed_document:
            self.generate_completed_document()

        return {
            'name': 'Signed Document',
            'type': 'ir.actions.act_url',
            'url': '/sign/download/%(request_id)s/%(access_token)s/completed' % {'request_id': self.id, 'access_token': self.access_token},
        }

    @api.multi
    def toggle_archived(self):
        self.ensure_one()
        self.archived = not self.archived

    @api.multi
    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self[0].favorited_ids else 4, self.env.user.id)]})

    @api.multi
    def action_draft(self):
        self.write({'completed_document': None, 'access_token': self._default_access_token(), 'state': 'draft'})

    @api.multi
    def action_sent(self, subject=None, message=None):
        self.write({'state': 'sent'})
        for signature_request in self:
            ignored_partners = []
            for request_item in signature_request.request_item_ids:
                if request_item.state != 'draft':
                    ignored_partners.append(request_item.partner_id.id)
            included_request_items = signature_request.request_item_ids.filtered(lambda r: not r.partner_id or r.partner_id.id not in ignored_partners)

            if signature_request.send_signature_accesses(subject, message, ignored_partners=ignored_partners):
                signature_request.send_follower_accesses(self.follower_ids, subject, message)
                included_request_items.action_sent()
            else:
                signature_request.action_draft()

    @api.multi
    def action_signed(self):
        self.write({'state': 'signed'})
        self.env.cr.commit()
        self.send_completed_document()

    @api.multi
    def action_canceled(self):
        self.write({'completed_document': None, 'access_token': self._default_access_token(), 'state': 'canceled'})
        for signature_request in self:
            signature_request.request_item_ids.action_draft()

    @api.one
    def set_signers(self, signers):
        self.request_item_ids.filtered(lambda r: not r.partner_id or not r.role_id).unlink()

        ids_to_remove = []
        for request_item in self.request_item_ids:
            for i in range(0, len(signers)):
                if signers[i]['partner_id'] == request_item.partner_id.id and signers[i]['role'] == request_item.role_id.id:
                    signers.pop(i)
                    break
            else:
                ids_to_remove.append(request_item.id)

        SignatureRequestItem = self.env['signature.request.item']
        SignatureRequestItem.browse(ids_to_remove).unlink()
        for signer in signers:
            SignatureRequestItem.create({
                'partner_id': signer['partner_id'],
                'signature_request_id': self.id,
                'role_id': signer['role']
            })

    @api.multi
    def send_signature_accesses(self, subject=None, message=None, ignored_partners=[]):
        self.ensure_one()
        if len(self.request_item_ids) <= 0 or (set(self.request_item_ids.mapped('role_id')) != set(self.template_id.signature_item_ids.mapped('responsible_id'))):
            return False

        self.request_item_ids.filtered(lambda r: not r.partner_id or r.partner_id.id not in ignored_partners).send_signature_accesses(subject, message)
        return True

    @api.one
    def send_follower_accesses(self, followers, subject=None, message=None):
        base_context = self.env.context
        template_id = self.env.ref('website_sign.website_sign_mail_template').id
        mail_template = self.env['mail.template'].browse(template_id)

        email_from_usr = self.create_uid.partner_id.name
        email_from_mail = self.create_uid.partner_id.email
        email_from = "%(email_from_usr)s <%(email_from_mail)s>" % {'email_from_usr': email_from_usr, 'email_from_mail': email_from_mail}

        for follower in followers:
            template = mail_template.sudo().with_context(base_context,
                lang = follower.lang,
                template_type = "follower",
                email_from_usr = email_from_usr,
                email_from_mail = email_from_mail,
                email_from = email_from,
                email_to = follower.email,
                link = "sign/document/%(request_id)s/%(access_token)s" % {'request_id': self.id, 'access_token': self.access_token},
                subject = subject or ("Signature request - " + self.reference),
                msgbody = (message or "").replace("\n", "<br/>")
            )
            template.send_mail(self.id, force_send=True)
        return True

    @api.multi
    def send_completed_document(self):
        self.ensure_one()
        if len(self.request_item_ids) <= 0 or self.state != 'signed':
            return False

        if not self.completed_document:
            self.generate_completed_document()

        base_context = self.env.context
        template_id = self.env.ref('website_sign.website_sign_mail_template').id
        mail_template = self.env['mail.template'].browse(template_id)

        email_from_usr = self.create_uid.partner_id.name
        email_from_mail = self.create_uid.partner_id.email
        email_from = "%(email_from_usr)s <%(email_from_mail)s>" % {'email_from_usr': email_from_usr, 'email_from_mail': email_from_mail}

        mail_template = mail_template.sudo().with_context(base_context,
            template_type = "completed",
            email_from_usr = email_from_usr,
            email_from_mail = email_from_mail,
            email_from = email_from,
            subject = "Signed Document - " + self.reference
        )

        for signer in self.request_item_ids:
            if not signer.partner_id:
                continue
            template = mail_template.with_context(
                lang = signer.partner_id.lang,
                email_to = signer.partner_id.email,
                link = "sign/document/%(request_id)s/%(access_token)s" % {'request_id': self.id, 'access_token': signer.access_token}
            )
            template.send_mail(self.id, force_send=True)

        for follower in self.follower_ids:
            template = mail_template.with_context(
                lang = follower.lang,
                email_to = follower.email,
                link = "sign/document/%(request_id)s/%(access_token)s" % {'request_id': self.id, 'access_token': self.access_token}
            )
            template.send_mail(self.id, force_send=True)

        mail_template.with_context( # Send copy to request creator
            email_to = email_from_mail,
            link = "sign/document/%(request_id)s/%(access_token)s" % {'request_id': self.id, 'access_token': self.access_token}
        ).send_mail(self.id, force_send=True)

        return True

    @api.one
    def generate_completed_document(self):
        if len(self.template_id.signature_item_ids) <= 0:
            self.completed_document = self.template_id.attachment_id.datas
            return

        old_pdf = PdfFileReader(io.BytesIO(base64.b64decode(self.template_id.attachment_id.datas)), overwriteWarnings=False)
        font = "Helvetica"
        normalFontSize = 0.015

        packet = io.BytesIO()
        can = canvas.Canvas(packet)
        itemsByPage = self.template_id.signature_item_ids.getByPage()
        SignatureItemValue = self.env['signature.item.value']
        for p in range(0, old_pdf.getNumPages()):
            page = old_pdf.getPage(p)
            width = float(page.mediaBox.getUpperRight_x())
            height = float(page.mediaBox.getUpperRight_y())

            # Set page orientation (either 0, 90, 180 or 270)
            rotation = page.get('/Rotate')
            if rotation:
                can.rotate(rotation)
                # Translate system so that elements are placed correctly
                # despite of the orientation
                if rotation == 90:
                    width, height = height, width
                    can.translate(0, -height)
                elif rotation == 180:
                    can.translate(-width, -height)
                elif rotation == 270:
                    width, height = height, width
                    can.translate(-width, 0)

            items = itemsByPage[p + 1] if p + 1 in itemsByPage else []
            for item in items:
                value = SignatureItemValue.search([('signature_item_id', '=', item.id), ('signature_request_id', '=', self.id)], limit=1)
                if not value or not value.value:
                    continue

                value = value.value

                if item.type_id.type == "text":
                    can.setFont(font, height*item.height*0.8)
                    can.drawString(width*item.posX, height*(1-item.posY-item.height*0.9), value)

                elif item.type_id.type == "textarea":
                    can.setFont(font, height*normalFontSize*0.8)
                    lines = value.split('\n')
                    y = (1-item.posY)
                    for line in lines:
                        y -= normalFontSize*0.9
                        can.drawString(width*item.posX, height*y, line)
                        y -= normalFontSize*0.1

                elif item.type_id.type == "signature" or item.type_id.type == "initial":
                    img = base64.b64decode(value[value.find(',')+1:])
                    can.drawImage(ImageReader(io.BytesIO(img)), width*item.posX, height*(1-item.posY-item.height), width*item.width, height*item.height, 'auto', True)

            can.showPage()

        can.save()

        item_pdf = PdfFileReader(packet, overwriteWarnings=False)
        new_pdf = PdfFileWriter()

        for p in range(0, old_pdf.getNumPages()):
            page = old_pdf.getPage(p)
            page.mergePage(item_pdf.getPage(p))
            new_pdf.addPage(page)

        output = io.BytesIO()
        new_pdf.write(output)
        self.completed_document = base64.b64encode(output.getvalue())
        output.close()

    @api.one
    def _message_post(self, message, partner=None, type='comment', subtype=False):
        return self.sudo(self.create_uid).message_post(
            body=message,
            author_id=(partner.id if partner else None),
            message_type=type,
            subtype=subtype
        )

    @api.model
    def initialize_new(self, id, signers, followers, reference, subject, message, send=True):
        signature_request = self.create({'template_id': id, 'reference': reference, 'follower_ids': [(6, 0, followers)], 'favorited_ids': [(4, self.env.user.id)]})
        signature_request.set_signers(signers)
        if send:
            signature_request.action_sent(subject, message)
            signature_request._message_post(_('Waiting for signatures.'), type='comment', subtype='mt_comment')
        return {
            'id': signature_request.id,
            'token': signature_request.access_token,
            'sign_token': signature_request.request_item_ids.filtered(lambda r: r.partner_id == self.env.user.partner_id).access_token,
        }

    @api.model
    def cancel(self, id):
        signature_request = self.browse(id)
        signature_request._message_post(_('Canceled.'), type='comment', subtype='mt_comment')
        return signature_request.action_canceled()

    @api.model
    def add_followers(self, id, followers):
        signature_request = self.browse(id)
        old_followers = set(signature_request.follower_ids.mapped('id'))
        signature_request.write({'follower_ids': [(6, 0, set(followers) | old_followers)]})
        signature_request.send_follower_accesses(self.env['res.partner'].browse(followers))
        return signature_request.id

class SignatureRequestItem(models.Model):
    _name = "signature.request.item"
    _description = "Signature Request"
    _rec_name = 'partner_id'

    @api.multi
    def _default_access_token(self):
        return str(uuid.uuid4())

    partner_id = fields.Many2one('res.partner', string="Partner", ondelete='cascade')
    signature_request_id = fields.Many2one('signature.request', string="Signature Request", ondelete='cascade', required=True)

    access_token = fields.Char('Security Token', required=True, default=_default_access_token, readonly=True)
    role_id = fields.Many2one('signature.item.party', string="Role")

    signature = fields.Binary(attachment=True)
    signing_date = fields.Date('Signed on', readonly=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("sent", "Waiting for completion"),
        ("completed", "Completed")
    ], readonly=True, default="draft")

    signer_email = fields.Char(related='partner_id.email')

    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))

    @api.multi
    def action_draft(self):
        self.write({
            'signature': None,
            'signing_date': None,
            'access_token': self._default_access_token(),
            'state': 'draft'
        })
        for request_item in self:
            itemsToClean = request_item.signature_request_id.template_id.signature_item_ids.filtered(lambda r: r.responsible_id == request_item.role_id or not r.responsible_id)
            self.env['signature.item.value'].search([('signature_item_id', 'in', itemsToClean.mapped('id')), ('signature_request_id', '=', request_item.signature_request_id.id)]).unlink()
        self.mapped('signature_request_id')._check_after_compute()

    @api.multi
    def action_sent(self):
        self.write({'state': 'sent'})
        self.mapped('signature_request_id')._check_after_compute()

    @api.multi
    def action_completed(self):
        self.write({'signing_date': time.strftime(DEFAULT_SERVER_DATE_FORMAT), 'state': 'completed'})
        self.mapped('signature_request_id')._check_after_compute()

    @api.multi
    def send_signature_accesses(self, subject=None, message=None):
        base_context = self.env.context
        template_id = self.env.ref('website_sign.website_sign_mail_template').id
        mail_template = self.env['mail.template'].browse(template_id)

        email_from_usr = self[0].create_uid.partner_id.name
        email_from_mail = self[0].create_uid.partner_id.email
        email_from = "%(email_from_usr)s <%(email_from_mail)s>" % {'email_from_usr': email_from_usr, 'email_from_mail': email_from_mail}

        for signer in self:
            if not signer.partner_id:
                continue
            template = mail_template.sudo().with_context(base_context,
                lang = signer.partner_id.lang,
                template_type = "request",
                email_from_usr = email_from_usr,
                email_from_mail = email_from_mail,
                email_from = email_from,
                email_to = signer.partner_id.email,
                link = "sign/document/%(request_id)s/%(access_token)s" % {'request_id': signer.signature_request_id.id, 'access_token': signer.access_token},
                subject = subject or ("Signature request - " + signer.signature_request_id.reference),
                msgbody = (message or "").replace("\n", "<br/>")
            )
            template.send_mail(signer.signature_request_id.id, force_send=True)

    @api.multi
    def sign(self, signature):
        self.ensure_one()
        if not isinstance(signature, dict):
            self.signature = signature
        else:
            SignatureItemValue = self.env['signature.item.value']
            request = self.signature_request_id

            signerItems = request.template_id.signature_item_ids.filtered(lambda r: not r.responsible_id or r.responsible_id.id == self.role_id.id)
            autorizedIDs = set(signerItems.mapped('id'))
            requiredIDs = set(signerItems.filtered('required').mapped('id'))

            itemIDs = {int(k) for k in signature}
            if not (itemIDs <= autorizedIDs and requiredIDs <= itemIDs): # Security check
                return False

            for itemId in signature:
                item_value = SignatureItemValue.search([('signature_item_id', '=', int(itemId)), ('signature_request_id', '=', request.id)])
                if not item_value:
                    item_value = SignatureItemValue.create({'signature_item_id': int(itemId), 'signature_request_id': request.id, 'value': signature[itemId]})
                    if item_value.signature_item_id.type_id.type == 'signature':
                        self.signature = signature[itemId][signature[itemId].find(',')+1:]
        return True

    @api.model
    def resend_access(self, id):
        self.browse(id).send_signature_accesses()
