# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Web Clearbit',
    'description': "Integrate Clearbit API to get company logo",
    'depends': ['web', 'base_setup'],
    'data': [
        'views/res_partner_views.xml',
        'views/web_clearbit_templates.xml'
    ],
    'qweb': [
        'static/src/xml/web_clearbit.xml'
    ],
    'auto_install': True,
}
