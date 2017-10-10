odoo.define('web_studio.ReportEditorSidebar', function (require) {
"use strict";

var core = require('web.core');
var relational_fields = require('web.relational_fields');
var StandaloneFieldManagerMixin = require('web.StandaloneFieldManagerMixin');
var Widget = require('web.Widget');

var Many2ManyTags = relational_fields.FieldMany2ManyTags;
var Many2One = relational_fields.FieldMany2One;

return Widget.extend(StandaloneFieldManagerMixin, {
    template: 'web_studio.ReportEditorSidebar',
    events: {
        'change input': '_onChangeReport',
        'click .o_web_studio_xml_editor': '_onXMLEditor',
        'click .o_web_studio_parameters': '_onParameters',
    },
    /**
     * @constructor
     * @param {Widget} parent
     * @param {Object} report
     */
    init: function (parent, report) {
        this._super.apply(this, arguments);
        StandaloneFieldManagerMixin.init.call(this);
        this.debug = core.debug;
        this.report = report;
    },
    /**
     * @override
     */
    willStart: function () {
        var self = this;
        // make record for the many2many groups
        var def1 = this.model.makeRecord('ir.model.fields', [{
            name: 'groups_id',
            fields: [{
                name: 'id',
                type: 'integer',
            }, {
                name: 'display_name',
                type: 'char',
            }],
            relation: 'res.groups',
            type: 'many2many',
            value: this.report.groups_id,
        }]).then(function (recordID) {
            self.groupsHandle = recordID;
        });
        // load record for the many2one paperformat
        var def2 = this.model.makeRecord('ir.model.fields', [{
            name: 'paperformat_id',
            relation: 'report.paperformat',
            type: 'many2one',
            value: this.report.paperformat_id,
        }]).then(function (recordID) {
            self.paperformatHandle = recordID;
        });
        var def3 = this._super.apply(this, arguments);
        return $.when(def1, def2, def3);
    },
    /**
     * @override
     */
    start: function () {
        var defs = [];
        defs.push(this._super.apply(this, arguments));
        var paperFormatRecord = this.model.get(this.paperformatHandle);
        var many2one = new Many2One(this, 'paperformat_id', paperFormatRecord, {
            mode: 'edit',
            attrs: {
                can_create: false,
                can_write: false,
            },
        });
        this._registerWidget(this.paperformatHandle, 'paperformat_id', many2one);
        defs.push(many2one.appendTo(this.$('.o_paperformat_id')));
        this.paperformatMany2one = many2one;

        // append many2many for groups_id
        var groupsRecord = this.model.get(this.groupsHandle);
        var many2many = new Many2ManyTags(this, 'groups_id', groupsRecord, {
            mode: 'edit',
        });
        this._registerWidget(this.groupsHandle, 'groups_id', many2many);
        defs.push(many2many.appendTo(this.$('.o_groups')));
        return $.when.apply($, defs);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onChangeReport: function (ev) {
        var $input = $(ev.currentTarget);
        var attribute = $input.attr('name');
        if (attribute) {
            var new_attrs = {};
            if ($input.attr('type') === 'checkbox') {
                new_attrs[attribute] = $input.is(':checked') ? 'True': '';
            } else {
                new_attrs[attribute] = $input.val();
            }
            this.trigger_up('studio_edit_report', {report: this.report, args: new_attrs});
        }
    },
    /**
     * @private
     * @override
     * @param {OdooEvent} ev
     */
    _onFieldChanged: function (ev) {
        StandaloneFieldManagerMixin._onFieldChanged.apply(this, arguments);

        var args = {};
        var field_name = ev.target.name;
        var record;
        if (field_name === 'groups_id') {
            record = this.model.get(this.groupsHandle);
            args[field_name] = record.data.groups_id.res_ids;
        } else if (field_name === 'paperformat_id') {
            args[field_name] = this.paperformatMany2one.value.res_id;
        }
        this.trigger_up('studio_edit_report', {
            report: this.report,
            args: args,
        });
    },
    /**
     * @private
     */
    _onParameters: function () {
        this.trigger_up('open_report_form');
    },
    /**
     * @private
     */
    _onXMLEditor: function () {
        this.trigger_up('open_xml_editor');
    },
});

});
