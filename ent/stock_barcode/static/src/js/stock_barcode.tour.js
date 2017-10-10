odoo.define('stock_barcode.tours', function(require) {
'use strict';

var Tour = require('web.Tour');

function scan_barcode(barcode) {
    odoo.__DEBUG__.services["web.core"].bus.trigger("barcode_scanned", barcode);
}

Tour.register({
    id:   "stock_barcode_inventory",
    name: "Inventory adjustment",
    mode: "test",
    steps: [
        {
            title:   "Click inventory button",
            element: ".button_inventory",
        },
        {
            waitFor: ".o_list_editable",
            title:   "Scan a location",
            onload: function() {
                scan_barcode("LOC-01-01-00");
            },
        },
        {
            waitFor: ".o_field_widget:contains('WH/Stock/Shelf 1')",
            title:   "Scan a product",
            onload: function() {
                scan_barcode("054398267125");
            },
        },
        {
            waitFor: ".o_list_editable td[data-field='product_id']:contains('[A1232] iPad Mini'),"
                   + ".o_list_editable td[data-field='location_id']:contains('WH/Stock/Shelf 1')"
                   + ".o_list_editable td[data-field='product_qty']:contains('1')",
            title:   "Rescan the same product",
            onload: function() {
                scan_barcode("054398267125");
            },
        },
        {
            waitFor: ".o_list_editable td[data-field='product_qty']:contains('2')",
            title:   "Scan another location",
            onload: function() {
                scan_barcode("LOC-01-02-00");
            },
        },
        {
            waitFor: ".o_field_widget:contains('WH/Stock/Shelf 2')",
            title:   "Rescan the same product",
            onload: function() {
                scan_barcode("054398267125");
            },
        },
        {
            waitFor: ".o_list_editable td[data-field='product_qty']:contains('1')",
            title:   "Scan button 'validate'",
            onload: function() {
                scan_barcode("O-BTN.validate");
            },
        },
        {
            waitFor: ".o_statusbar_status .btn-primary:contains('Validated')",
            title:   "Done",
        },
    ]
});

Tour.register({
    id:   "stock_barcode_out_picking",
    name: "Delivery order",
    mode: "test",
    steps: [
        {
            title:   "Scan a delivery order",
            onload: function() {
                scan_barcode("WH/OUT/00005");
            },
        },
        {
            waitFor: ".o_list_editable td[data-field='product_id']:contains('[A1232] iPad Mini'),"
                   + ".o_list_editable td[data-field='qty_done']:contains('0')",
            title:   "Scan the product 5 times",
            onload: function() {
                for (var i = 0; i < 5; i++) {
                    scan_barcode("054398267125");
                }
            },
        },
        {
            waitFor: ".o_list_editable td[data-field='qty_done']:contains('5')",
            title:   "Scan a pack",
            onload: function() {
                scan_barcode("PACK0000001");
            },
        },
        {
            waitFor: ".o_list_editable td[data-field='to_loc']:contains('Customers : PACK0000001')",
            title:   "Scan the remaining 75 items",
            onload: function() {
                for (var i = 0; i < 75; i++) {
                    scan_barcode("054398267125");
                }
            },
        },
        {
            waitFor: ".o_list_editable td[data-field='qty_done']:contains('75')",
            title:   "Complete the picking and scan button 'validate'",
            onload: function() {
                scan_barcode("O-BTN.validate");
            },
        },
        {
            waitFor: ".o_statusbar_status .btn-primary:contains('Validated')",
            title:   "Done",
        },
    ]
});

Tour.register({
    id:   "stock_barcode_in_picking",
    name: "Incoming shipment with lots encoding",
    mode: "test",
    steps: [
        {
            title:   "Scan an incoming shipment",
            onload: function() {
                scan_barcode("WH/IN/00003");
            },
        },
        {
            waitFor: ".o_list_editable",
            title:   "Scan the product",
            onload: function() {
                scan_barcode("420196872340");
            },
        },
        // Here, the 'wizard' to scan lots/serial numbers should open
        {
            waitFor: ".modal-dialog .o_list_editable",
            title:   "Scan a lot number",
            onload: function() {
                scan_barcode("LOT-000001");
            },
        },
        {
            waitFor: ".modal-dialog .o_list_editable td[data-field='lot_name']:contains('LOT-000001')",
            title:   "Scan 'validate'",
            onload: function() {
                scan_barcode("O-BTN.validate");
            },
        },
        {
            waitFor: ".o_list_editable td[data-field='qty_done']:contains('1')",
        },
    ]
});

});
