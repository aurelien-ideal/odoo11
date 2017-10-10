odoo.define('stock_barcode.MainMenu', function (require) {
"use strict";

var core = require('web.core');
var Widget = require('web.Widget');
var Dialog = require('web.Dialog');
var Session = require('web.session');

var _t = core._t;

var MainMenu = Widget.extend({
    template: 'main_menu',

    events: {
        "click .button_operations": function(){
            this.do_action('stock_barcode.stock_picking_type_action_kanban');
        },
        "click .button_inventory": function(){
            this.open_inventory();
        },
    },

    init: function(parent, action) {
        // Yet, "_super" must be present in a function for the class mechanism to replace it with the actual parent method.
        this._super.apply(this, arguments);
        this.message_demo_barcodes = action.params.message_demo_barcodes;
    },

    start: function() {
        var self = this;
        core.bus.on('barcode_scanned', this, this._onBarcodeScanned);
        return this._super().then(function() {
            if (self.message_demo_barcodes) {
                self.setup_message_demo_barcodes();
            }
        });
    },

    destroy: function () {
        core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
        this._super();
    },

    setup_message_demo_barcodes: function() {
        var self = this;
        // Upon closing the message (a bootstrap alert), propose to remove it once and for all
        self.$(".message_demo_barcodes").on('close.bs.alert', function () {
            var message = _t("Do you want to permanently remove this message ?\
                It won't appear anymore, so make sure you don't need the barcodes sheet or you have a copy.");
            var options = {
                title: _t("Don't show this message again"),
                size: 'medium',
                buttons: [
                    { text: _t("Remove it"), close: true, classes: 'btn-primary', click: function() {
                        Session.rpc('/stock_barcode/rid_of_message_demo_barcodes');
                    }},
                    { text: _t("Leave it"), close: true }
                ],
            };
            Dialog.confirm(self, message, options);
        });
    },

    _onBarcodeScanned: function(barcode) {
        var self = this;
        if (!$.contains(document, this.el)) {
            return;
        }
        Session.rpc('/stock_barcode/scan_from_main_menu', {
            barcode: barcode,
        }).then(function(result) {
            if (result.action) {
                self.do_action(result.action);
            } else if (result.warning) {
                self.do_warn(result.warning);
            }
        });
    },

    open_inventory: function() {
        var self = this;
        return this._rpc({
                model: 'stock.inventory',
                method: 'open_new_inventory',
            })
            .then(function(result) {
                self.do_action(result);
            });
    },
});

core.action_registry.add('stock_barcode_main_menu', MainMenu);

return {
    MainMenu: MainMenu,
};

});
