# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Odoo Mexican Localization Reports",
    "summary": """
        Electronic accounting reports
            - COA
            - Trial Balance
        DIOT Report
    """,
    "version": "10.0.1.0.0",
    "author": "Vauxoo",
    "category": "Accounting",
    "website": "http://www.vauxoo.com",
    "license": "OEEL-1",
    "depends": [
        "account_reports",
        "l10n_mx",
    ],
    "demo": [
        "demo/res_company_demo.xml",
        "demo/account_invoice_demo.yml",
        "demo/res_partner_demo.xml",
    ],
    "data": [
        "data/account_financial_report_data.xml",
        "data/country_data.xml",
        "data/templates/cfdi11coa.xml",
        "data/templates/cfdi11balance.xml",
        "views/res_country_view.xml",
        "views/res_partner_view.xml",
    ],
    "installable": True,
    "auto_install": True,
}
