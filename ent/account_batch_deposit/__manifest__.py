# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Batch Deposit',
    'version': '1.0',
    'category': 'Accounting',
    'description': """
Batch Deposit
=============
Batch deposits allows you to group received checks before you deposit them to the bank.
The amount deposited to your bank will then appear as a single transaction on your bank statement.
When you proceed with the reconciliation, simply select the corresponding batch deposit to reconcile the payments.
    """,
    'website': 'https://www.odoo.com/page/accounting',
    'depends' : ['account_accountant'],
    'data': [
        'security/account_batch_deposit_security.xml',
        'security/ir.model.access.csv',
        'data/account_batch_deposit_data.xml',
        'report/account_batch_deposit_reports.xml',
        'report/account_batch_deposit_report_templates.xml',
        'views/account_batch_deposit_templates.xml',
        'views/account_batch_deposit_views.xml',
        'views/account_journal_views.xml',
    ],
    'qweb': [
        "static/src/xml/account_reconciliation.xml",
    ],
    'test': [],
    'installable': True,
    'license': 'OEEL-1',
}
