# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Subscription Management',
    'version': '1.1',
    'category': 'Sales',
    'summary': 'Recurring invoicing, renewals',
    'description': """
This module allows you to manage subscriptions.

Features:
    - Create & edit subscriptions
    - Modify subscriptions with sales orders
    - Generate invoice automatically at fixed intervals
""",
    'author': 'Camptocamp / Odoo',
    'depends': [
        'sale_management',
        'portal',
        'sale_payment',
    ],
    'data': [
        'security/sale_subscription_security.xml',
        'security/ir.model.access.csv',
        'wizard/sale_subscription_close_reason_wizard_views.xml',
        'wizard/sale_subscription_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'views/res_partner_views.xml',
        'views/account_analytic_account_views.xml',
        'views/sale_subscription_views.xml',
        'views/assets.xml',
        'views/subscription_portal_templates.xml',
        'views/res_config_settings_views.xml',
        'views/payment_views.xml',
        'data/sale_subscription_data.xml',
        'data/mail_template_data.xml',
        'report/sale_subscription_report_view.xml',
    ],
    'demo': [
        'data/sale_subscription_demo.xml'
    ],
    'application': True,
    'license': 'OEEL-1',
}
