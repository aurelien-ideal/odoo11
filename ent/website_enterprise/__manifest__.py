# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Website Enterprise',
    'category': 'Website',
    'description': """
Override community website features
    """,
    'depends': ['website'],
    'data': [
        'views/website_enterprise_templates.xml'
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
