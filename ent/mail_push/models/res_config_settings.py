# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mail_push_notification = fields.Boolean('Notifications', oldname="default_mail_push_notification")
    fcm_api_key = fields.Char('Server API Key')
    fcm_project_id = fields.Char('Sender ID')

    def get_fcm_credentials(self):
        params = self.env['ir.config_parameter'].sudo()
        return dict(
            mail_push_notification=params.get_param('mail_push.mail_push_notification', default=False),
            fcm_api_key=params.get_param('mail_push.fcm_api_key', default=''),
            fcm_project_id=params.get_param('mail_push.fcm_project_id', default=''),
        )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(self.get_fcm_credentials())
        return res

    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param("mail_push.mail_push_notification", self.mail_push_notification)
        params.set_param('mail_push.fcm_api_key', self[0].fcm_api_key or '')
        params.set_param('mail_push.fcm_project_id', self[0].fcm_project_id or '')
