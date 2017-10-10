# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'UPS Bill My Account',
    'category': 'Website',
    'description': """
This module will give an option of bill my account on ups delivery methods
==========================================================================
    """,
    'depends': ['delivery_ups', 'website_sale_delivery'],
    'data': [
        'data/payment_acquirer_data.xml',
        'views/delivery_ups_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'auto_install': True,
}
