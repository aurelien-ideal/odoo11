# -*- coding: utf-8 -*-
{
    'name': "Online Subscription Quotes",
    'auto-install': True,
    'depends': ['sale_subscription', 'website_quote'],

    'summary': """
        Online Quotes for subscriptions products""",

    'description': """
Subscription integration  the Online Quotes
-------------------------------------------

Categorize the lines per subscription template when an online quote contains subscription products.
    """,

    'data': [
        'views/templates.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
}
