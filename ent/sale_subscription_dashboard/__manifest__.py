# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sale Subscription Dashboard',
    'version': '1.0',
    'depends': ['sale_subscription_asset', 'account_deferred_revenue'],
    'description': """
Sale Subscription Dashboard
===========================
It adds dashboards to :
1) Analyse the recurrent revenue and other metrics for subscriptions
2) Analyse the subscriptions modifications by salesman and compute their value.
    """,
    'website': 'https://www.odoo.com/page/accounting',
    'category': 'Accounting & Finance',
    'data': [
        'views/sale_subscription_dashboard_views.xml',
        'views/sale_subscription_dashboard_templates.xml',
    ],
    'demo': [
    ],
    'qweb': [
        "static/src/xml/sale_subscription_dashboard.xml",
    ],
    'installable': True,
    'application': False,
    'license': 'OEEL-1',
}
