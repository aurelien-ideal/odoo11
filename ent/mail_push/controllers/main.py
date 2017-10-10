# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request


class Main(http.Controller):

    @http.route("/mobile/push_uuid", auth='user', type='json')
    def mobile_push_uuid(self):
        return request.env['mail.channel']._get_mobile_push_uuid()
