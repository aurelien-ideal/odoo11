# -*- coding: utf-8 -*-
{
    'name': "SEPA Credit Transfer in Expenses",
    'summary': """Export expenses payments as SEPA Credit Transfer files""",
    'category': 'Accounting',
    'description': """
        Enable the SEPA features in the payments of expenses
    """,
    'category': 'Accounting &amp; Finance',
    'version': '1.0',
    'depends': ['account_sepa', 'hr_expense'],
    'auto_install': True,
    'data': [
        'views/payment.xml',
    ],
    'license': 'OEEL-1',
}
