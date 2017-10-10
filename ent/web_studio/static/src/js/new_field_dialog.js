odoo.define('web_studio.NewFieldDialog', function (require) {
"use strict";

var core = require('web.core');
var Dialog = require('web.Dialog');
var relational_fields = require('web.relational_fields');
var ModelFieldSelector = require('web.ModelFieldSelector');
var StandaloneFieldManagerMixin = require('web.StandaloneFieldManagerMixin');

var _t = core._t;
var Many2one = relational_fields.FieldMany2One;

// TODO: refactor this file

var NewFieldDialog = Dialog.extend(StandaloneFieldManagerMixin, {
    template: 'web_studio.NewFieldDialog',
    /**
     * @constructor
     * @param {String} model_name
     * @param {String} ttype
     * @param {Object} fields
     */
    init: function (parent, model_name, ttype, fields) {
        this.model_name = model_name;
        this.ttype = ttype;
        this.fields = fields;
        var options = {
            title: _t('Add a field'),
            size: 'small',
            buttons: [{
                text: _t("Confirm"),
                classes: 'btn-primary',
                click: this._onSave.bind(this)
            }, {
                text: _t("Cancel"),
                close: true
            }],
        };
        this._super(parent, options);
        StandaloneFieldManagerMixin.init.call(this);
    },
    /**
     * @override
     */
    start: function() {
        var self = this;
        var defs = [];
        var record;
        var options = {
            mode: 'edit',
        };

        this.$modal.addClass('o_web_studio_field_modal');

        if (this.ttype === 'one2many') {
            defs.push(this.model.makeRecord('ir.model.fields', [{
                name: 'field',
                relation: 'ir.model.fields',
                type: 'many2one',
                domain: [['relation', '=', this.model_name], ['ttype', '=', 'many2one']],
            }], {
                'field': {
                    can_create: false,
                }
            }).then(function (recordID) {
                record = self.model.get(recordID);
                self.many2one_field = new Many2one(self, 'field', record, options);
                self._registerWidget(recordID, 'field', self.many2one_field);
                self.many2one_field.nodeOptions.no_create_edit = !core.debug;
                self.many2one_field.appendTo(self.$('.o_many2one_field'));
            }));
        } else if (_.contains(['many2many', 'many2one'], this.ttype)) {
            defs.push(this.model.makeRecord('ir.model', [{
                name: 'model',
                relation: 'ir.model',
                type: 'many2one',
                domain: [['transient', '=', false], ['abstract', '=', false]]
            }]).then(function (recordID) {
                record = self.model.get(recordID);
                self.many2one_model = new Many2one(self, 'model', record, options);
                self._registerWidget(recordID, 'model', self.many2one_model);
                self.many2one_model.nodeOptions.no_create_edit = !core.debug;
                self.many2one_model.appendTo(self.$('.o_many2one_model'));
            }));
        } else if (this.ttype === 'related') {
            // This restores default modal height (bootstrap) and allows field selector to overflow
            this.$el.css("overflow", "visible").closest(".modal-dialog").css("height", "auto");
            var field_options = {
                fields: _.filter(this.fields, {type: 'many2one'}),
                readonly: false,
            };
            this.fieldSelector = new ModelFieldSelector(this, this.model_name, [], field_options);
            defs.push(this.fieldSelector.appendTo(this.$('.o_many2one_field')));
        }

        defs.push(this._super.apply(this, arguments));
        return $.when.apply($, defs);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onSave: function() {
        var values = {};
        if (this.ttype === 'one2many') {
            values.relation_field_id = this.many2one_field.value.res_id;
        } else if (_.contains(['many2many', 'many2one'], this.ttype)) {
            values.relation_id = this.many2one_model.value.res_id;
            values.field_description = this.many2one_model.m2o_value;
        } else if (this.ttype === 'selection') {
            values.selection = [];
            var selection_list = _.map(this.$('#selectionItems').val().split("\n"),function(value) {
                value = value.trim();
                if (value) {
                    return value;
                }
            });
            selection_list = _.reject(_.uniq(selection_list), _.isUndefined.bind());
            values.selection = _.map(selection_list, function(value) {
                return [value, value];
            });
        } else if (this.ttype === 'related') {
            values.related = this.fieldSelector.chain.join('.');
            values.ttype = this.fieldSelector.getSelectedField().type;
        }
        this.trigger('field_default_values_saved', values);
    },
});

return NewFieldDialog;

});
