# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mrp Workorder',
    'version': '1.0',
    'category': 'Manufacturing',
    'sequence': 51,
    'summary': """Work Orders, Planing, Stock Reports.""",
    'depends': ['mrp'],
    'description': """Enterprise extension for MRP

* Work order planning.  Check planning by Gantt views grouped by production order / work center
* Traceability report
* Cost Structure report (mrp_account)""",
    'data': [
        'views/mrp_production_views.xml',
        'views/mrp_routing_views.xml',
    ],
    'demo': [
        'data/mrp_production_demo.xml'
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
