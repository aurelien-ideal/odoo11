# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Account Extension",
    'description': """
        Adapt base accounting module for Enterprise Edition.

        This module will be auto installed if account module and enterprise edition are present
    """,
    'category': 'Hidden',
    'version': '1.0',
    'depends': ['account'],
    'data': [
        'views/account_report_menu_invisible.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
