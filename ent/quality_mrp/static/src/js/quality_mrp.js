odoo.define('quality_mrp.update_kanban', function (require) {
"use strict";

var basic_fields = require('web.basic_fields');
var core = require('web.core');
var field_registry = require('web.field_registry');
var KanbanController = require('web.KanbanController');
var KanbanRecord = require('web.KanbanRecord');
var KanbanView = require('web.KanbanView');
var view_registry = require('web.view_registry');
var ControlPanel = require('web.ControlPanel');

var FieldInteger = basic_fields.FieldInteger;
var FieldBinaryImage = basic_fields.FieldBinaryImage;

ControlPanel.include({
    _render_breadcrumbs: function (breadcrumbs) {
        var found = false;
        _.each(breadcrumbs, function(data) {
            if (data.action.action_descr.xml_id === "quality_mrp.mrp_workorder_action_tablet") {
                found = true;
            }
        });
        return this._super( found ? [] : breadcrumbs)
    },
});

KanbanRecord.include({
    _openRecord: function () {
        if (this.modelName === 'mrp.workorder') {
            var self = this;
            this._rpc({
                method: 'open_tablet_view',
                model: self.modelName,
                args: [self.id],
            }).then(function (result) {
                self.do_action(result);
            });
        } else {
            this._super.apply(this, arguments);
        }
    },
});

var BackArrow = FieldInteger.extend({
    events: {
        'click': '_onClick',
    },
    _render: function () {
        this.$el.html('<button class="btn btn-default o_workorder_icon_btn o_workorder_icon_back"><i class="fa fa-arrow-left"/></button>');
    },
    _onClick: function() {
        var self = this;
        this._rpc({
            method: 'action_back',
            model: 'mrp.workorder',
            args: [self.recordData.id],
        }).then(function () {
            self.do_action('quality_mrp.mrp_workorder_action_tablet', {
                additional_context: {active_id: self.record.data.workcenter_id.res_id},
                clear_breadcrumbs: true,
            });
        });
    },
});

var TabletImage = FieldBinaryImage.extend({
    template: 'FieldBinaryTabletImage',
});

var TabletKanbanController = KanbanController.extend({
    renderButtons: function ($node) {
        var self = this;
        this.$buttons = $('<div/>')
        this.$buttons.html('<button class="btn btn-default back-button"><i class="fa fa-arrow-left"/></button>');
        this.$buttons.on('click', function () {
            self.do_action('mrp.mrp_workcenter_kanban_action', {clear_breadcrumbs: true});
        });
        this.$buttons.appendTo($node);
    },
});

var TabletKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: TabletKanbanController,
    }),
});

field_registry.add('back_arrow', BackArrow);
field_registry.add('tablet_image', TabletImage);
view_registry.add('tablet_kanban_view', TabletKanbanView);
});
