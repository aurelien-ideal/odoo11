# -*- coding: utf-8 -*-
{
    'name': 'Sign',
    'version': '1.0',
    'category': 'Document Management',
    'summary': "Send documents to sign online, receive and archive filled copies (esign)",
    'description': """
Sign and complete your documents easily. Customize your documents with text and signature fields and send them to your recipients.\n
Let your customers follow the signature process easily.
    """,
    'website': 'http://www.odoo.com',
    'depends': ['mail', 'document', 'portal'],
    'data': [
        'security/ir.model.access.csv',

        'views/signature_request_templates.xml',
        'views/signature_request_template_templates.xml',

        'views/signature_request_views.xml',
        'views/signature_request_template_views.xml',

        'data/signature_request_data.xml',
        'data/signature_request_template_data.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'demo': [
        'data/signature_request_template_demo.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'OEEL-1',
}
