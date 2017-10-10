# -*- coding: utf-8 -*-
{
    'name': "Firebase Cloud Messaging",
    'version': "1.0",
    'summary': 'Push notification for mobile app',
    'description': """
Google Firebase Messaging Integration
=====================================
This module allows to send FCM push notification on registered mobiles
for every message in chatter.

**Configure your API keys from General Setting**
    """,
    'depends': ['mail', 'web_mobile'],
    'data': [
        'views/mail_push_templates.xml',
        'views/res_config_settings_views.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
