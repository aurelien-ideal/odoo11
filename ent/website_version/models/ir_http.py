# -*- coding: utf-8 -*-

from odoo.http import request
from odoo.osv import orm
import json


class ir_http(orm.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls):
        x = super(ir_http, cls)._dispatch()
        if request.context.get('website_version_experiment'):
            data=json.dumps(request.context['website_version_experiment'], ensure_ascii=False)
            x.set_cookie('website_version_experiment', data)
        return x
