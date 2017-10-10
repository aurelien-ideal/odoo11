# -*- coding: utf-8 -*-

{
    'name': "Warehouse Management Barcode Scanning",
    'summary': "Add barcode scanning facilities to Warehouse Management.",
    'description': """
        This module adds support for barcodes scanning to the warehouse management system.
    """,
    'category': 'Warehouse',
    'version': '1.0',
    'depends': ['barcodes', 'stock'],
    'data': [
        'views/inherited_stock_inventory_views.xml',
        'views/inherited_stock_picking_views.xml',
        'views/stock_barcode_templates.xml',
        'views/stock_barcode_views.xml',
        'views/res_config_settings_views.xml',
        'views/inherited_stock_scrap_views.xml',
        'data/web_planner_data.xml',
        'wizard/stock_barcode_lot_view.xml',
    ],
    'qweb': [
        "static/src/xml/stock_barcode.xml",
    ],
    'demo': [
        'data/demo.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OEEL-1',
}
