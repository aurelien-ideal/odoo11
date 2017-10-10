# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Website Form Helpdesk',
    'category': 'Helpdesk',
    'sequence': 58,
    'summary': 'Allow website visitors to submit tickets through a form',
    'depends': [
        'website_form_editor',
        'website_helpdesk',
    ],
    'description': """
Website form integration for the helpdesk module
================================================

    Allow customers to easily submit tickets through a form on your website.

    """,
    'data': [
        'data/website_helpdesk.xml',
        'views/helpdesk_views.xml',
        'views/helpdesk_templates.xml'
    ],
    'license': 'OEEL-1',
}
