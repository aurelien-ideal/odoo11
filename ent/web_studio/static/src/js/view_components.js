odoo.define('web_studio.view_components', function (require) {
"use strict";

var core = require('web.core');
var Registry = require('web.Registry');
var Widget = require('web.Widget');

var _t = core._t;

var AbstractComponent = Widget.extend({
    structure: false,
    label: false,
    description: false,
    /**
     * @override
     */
    start: function () {
        this.$el.addClass('o_web_studio_component');
        this.$el.data('structure', this.structure);
        this.$el.text(this.label);
        if (core.debug && this.description) {
            this.$el.addClass('o_web_studio_debug');
            this.$el.append($('<div>')
                .addClass('o_web_studio_component_description')
                .text(this.description)
            );
        }
        this.$el.draggable({
            helper: 'clone',
            opacity: 0.4,
            scroll: false,
            revert: 'invalid',
            revertDuration: 200,
            refreshPositions: true,
            start: function (e, ui) {
                $(ui.helper).addClass("ui-draggable-helper");
            }
        });
        return this._super.apply(this, arguments);
    },
});

var NotebookComponent = AbstractComponent.extend({
    structure: 'notebook',
    label: _t('Tabs'),
    ttype: 'tabs',
    className: 'o_web_studio_field_tabs',
});
var GroupComponent = AbstractComponent.extend({
    structure: 'group',
    label: _t('Columns'),
    ttype: 'columns',
    className: 'o_web_studio_field_columns',
});
var FilterComponent = AbstractComponent.extend({
    structure: 'filter',
    label: _t('Filter'),
    ttype: 'filter',
    className: 'o_web_studio_filter',
});
var FilterSeparatorComponent = AbstractComponent.extend({
    structure: 'separator',
    label: _t('Separator'),
    ttype: 'separator',
    className: 'o_web_studio_filter_separator',
});
var AbstractNewFieldComponent = AbstractComponent.extend({
    structure: 'field',
    ttype: false,
    /**
     * @override
     */
    start: function () {
        this.description = this.ttype;
        this.$el.data('field_description', {
            ttype: this.ttype,
            field_description: 'New ' + this.label,
        });
        return this._super();
    },
});
var CharFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'char',
    label: _t('Text'),
    className: 'o_web_studio_field_char',
});
var TextFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'text',
    label: _t('Multiline Text'),
    className: 'o_web_studio_field_text',
});
var IntegerFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'integer',
    label: _t('Integer number'),
    className: 'o_web_studio_field_integer',
});
var DecimalFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'float',
    label: _t('Decimal Number'),
    className: 'o_web_studio_field_float',
});
var HtmlFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'html',
    label: _t('Html'),
    className: 'o_web_studio_field_html',
});
var MonetaryFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'monetary',
    label: _t('Monetary'),
    className: 'o_web_studio_field_monetary',
});
var DateFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'date',
    label: _t('Date'),
    className: 'o_web_studio_field_date',
});
var DatetimeFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'datetime',
    label: _t('Date & Time'),
    className: 'o_web_studio_field_datetime',
});
var BooleanFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'boolean',
    label: _t('Checkbox'),
    className: 'o_web_studio_field_boolean',
});
var SelectionFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'selection',
    label: _t('Selection'),
    className: 'o_web_studio_field_selection',
});
var BinaryFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'binary',
    label: _t('File'),
    className: 'o_web_studio_field_binary',
});

var Many2manyFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'many2many',
    label: _t('Many2many'),
    className: 'o_web_studio_field_many2many',
});
var One2manyFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'one2many',
    label: _t('One2many'),
    className: 'o_web_studio_field_one2many',
});
var Many2oneFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'many2one',
    label: _t('Many2one'),
    className: 'o_web_studio_field_many2one',
});

var ExistingFieldComponent = AbstractComponent.extend({
    /**
     * @override
     * @param {Widget} parent
     * @param {String} name
     * @param {String} field_description
     * @param {String} ttype
     * @param {Boolean} store
     */
    init: function (parent, name, field_description, ttype, store) {
        this._super(parent);
        this.structure = 'field';
        this.label = field_description;
        this.description = name;
        this.className = 'o_web_studio_field_' + ttype;
        this.ttype = ttype;
        this.store = store;
    },
    /**
     * @override
     */
    start: function () {
        this.$el.data('new_attrs',{
            name: this.description,
            label: this.label,
            ttype: this.ttype,
            store: this.store ? "true":"false",
        });
        return this._super.apply(this, arguments);
    },
});

var AbstractNewWidgetComponent = AbstractNewFieldComponent.extend({
    attrs: {},
    /**
     * @override
     */
    start: function () {
        this.$el.data('new_attrs', this.attrs);
        return this._super.apply(this, arguments);
    },
});
var ImageWidgetComponent = AbstractNewWidgetComponent.extend({
    ttype: 'binary',
    label: _t('Image'),
    className: 'o_web_studio_field_picture',
    attrs: {widget: 'image'},
});
var TagWidgetComponent = AbstractNewWidgetComponent.extend({
    ttype: 'many2many',
    label: _t('Tags'),
    className: 'o_web_studio_field_tags',
    attrs: {widget: 'many2many_tags'},
});
var PriorityWidgetComponent = AbstractNewWidgetComponent.extend({
    ttype: 'selection',
    label: _t('Priority'),
    className: 'o_web_studio_field_priority',
    attrs: {widget: 'priority'},
});
var RelatedFieldComponent = AbstractNewFieldComponent.extend({
    ttype: 'related',
    label: _t('Related Field'),
    className: 'o_web_studio_field_related',
});
var form_component_widget_registry = new Registry();
form_component_widget_registry
    .add('form_components', [
        NotebookComponent,
        GroupComponent,
    ])
    .add('search_components', [
        FilterComponent,
        FilterSeparatorComponent,
    ])
    .add('new_field', [
        CharFieldComponent,
        TextFieldComponent,
        IntegerFieldComponent,
        DecimalFieldComponent,
        HtmlFieldComponent,
        MonetaryFieldComponent,
        DateFieldComponent,
        DatetimeFieldComponent,
        BooleanFieldComponent,
        SelectionFieldComponent,
        BinaryFieldComponent,
        One2manyFieldComponent,
        Many2oneFieldComponent,
        Many2manyFieldComponent,
        ImageWidgetComponent,
        TagWidgetComponent,
        PriorityWidgetComponent,
        RelatedFieldComponent,
    ])
    .add('existing_field', ExistingFieldComponent);

return {
    registry: form_component_widget_registry,
};

});
