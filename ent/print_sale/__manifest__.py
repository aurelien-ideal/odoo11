# -*- coding: utf-8 -*-
{
    'name': 'Print Sale',
    'summary': 'Print and Send Sales Orders',
    'category': 'Sales',
    'version': '1.0',
    'description': """Print and Send your Sales Order by Post""",
    'depends': ['print', 'sale_management'],
    'data': [
        'wizard/print_document_partner_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
