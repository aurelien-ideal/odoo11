# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MailActivityType(models.Model):
    _inherit = 'mail.activity.type'

    create_voip_phonecall = fields.Boolean(
        'Generates a voip phonecall',
        help='If set to true, when an activity of this type is scheduled, a voip phonecall is created'
    )


class MailActivity(models.Model):
    _inherit = 'mail.activity'
    phone = fields.Char('Phone')
    mobile = fields.Char('Mobile')
    voip_phonecall_id = fields.Many2one('voip.phonecall', 'Linked Voip Phonecall')
    is_call_type = fields.Boolean(
        'Is it a call type activity?', compute='_compute_is_call_type',
    )

    @api.depends('activity_type_id')
    def _compute_is_call_type(self):
        for activity in self:
            activity.is_call_type = activity.activity_type_id.create_voip_phonecall

    @api.model
    def create(self, values):
        activity = super(MailActivity, self).create(values)
        if activity.activity_type_id.create_voip_phonecall:
            numbers = activity._compute_phonenumbers()
            if numbers['phone'] or numbers['mobile']:
                activity.phone = numbers['phone']
                activity.mobile = numbers['mobile']
                phonecall = self.env['voip.phonecall'].create_from_activity(activity)
                activity.voip_phonecall_id = phonecall.id
                notification = {'type': 'refresh_voip'}
                self.env['bus.bus'].sendone(
                    (self._cr.dbname, 'res.partner', activity.user_id.partner_id.id),
                    notification
                )
        return activity

    @api.multi
    def _compute_phonenumbers(self):
        self.ensure_one()
        model = self.env[self.res_model]
        record = model.browse(self.res_id)
        numbers = {
            'phone': False,
            'mobile': False,
        }
        if 'phone' in record:
            numbers['phone'] = record.phone
        if 'mobile' in record:
            numbers['mobile'] = record.mobile
        if not numbers['phone'] and not numbers['mobile']:
            fields = model._fields.items()
            partner_field_name = [k for k, v in fields if v.type == 'many2one' and v.comodel_name == 'res.partner']
            if partner_field_name:
                numbers['phone'] = record[partner_field_name[0]].phone
                numbers['mobile'] = record[partner_field_name[0]].mobile
        return numbers

    @api.multi
    def action_feedback(self, feedback=False):
        self.ensure_one()
        phonecall = self.voip_phonecall_id
        user_id = self.user_id.partner_id.id
        note = self.note
        mail_message_id = super(MailActivity, self).action_feedback(feedback)
        if phonecall:
            vals = {
                'state': 'done',
                'mail_message_id': mail_message_id,
                'note': feedback if feedback else note,
            }
            if not phonecall.call_date:
                vals.update(call_date=fields.Datetime.now())
            phonecall.write(vals)
            self.env['bus.bus'].sendone(
                (self._cr.dbname, 'res.partner', user_id),
                {'type': 'refresh_voip'}
            )
        return mail_message_id
