odoo.define('web_studio.ReportEditor', function (require) {
"use strict";

var ReportAction = require('report.client_action');
var core = require('web.core');
var data_manager = require('web.data_manager');
var session = require('web.session');

var ReportEditorSidebar = require('web_studio.ReportEditorSidebar');
var XMLEditor = require('web_studio.XMLEditor');

var QWeb = core.qweb;


var ReportEditor = ReportAction.extend({

    template: 'web_studio.report_editor',
    custom_events: {
        'studio_edit_report': '_onEditReport',
        'open_report_form': '_onOpenReportForm',
        'open_xml_editor': '_onOpenXMLEditor',
        'close_xml_editor': '_onCloseXMLEditor',
        'save_xml_editor': '_onSaveXMLEditor',
    },
    /**
     * @constructor
     * @param {Widget} parent
     * @param {Object} action
     * @param {Object} [options]
     */
    init: function (parent, action, options) {
        options = options || {};
        options = _.extend(options, {
            report_url: '/report/html/' + action.report_name + '/' + action.active_ids + '?studio=1',
            report_name: action.report_name,
            report_file: action.report_file,
            name: action.name,
            display_name: action.display_name,
            context: {
                active_ids: action.active_ids.split(','),
            },
        });
        this.view_id = action.view_id;
        this.res_model = 'ir.actions.report';
        this.res_id = action.id;
        this._super(parent, action, options);
    },
    /**
     * @override
     */
    willStart: function () {
        var self = this;

        return this._super.apply(this, arguments).then(function () {
            return self._rpc({
                    model: 'ir.actions.report',
                    method: 'read',
                    args: [[self.res_id]],
                })
                .then(function (report) {
                    self.sidebar = new ReportEditorSidebar(self, report[0]);
                });
        });
    },
    /**
     * @override
     */
    start: function () {
        var self = this;

        return this._super.apply(this, arguments).then(function () {
            return self.sidebar.prependTo(self.$el);
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} report
     * @param {Object} values
     * @returns {Deferred}
     */
    _editReport: function (report, values) {
        return this._rpc({
            route: '/web_studio/edit_report',
            params: {
                report_id: report.id,
                values: values,
                context: session.user_context,
            },
        });
    },
    /**
     * This is used when the view is edited with the XML editor: the whole arch
     * is replaced by a new one.
     *
     * @private
     * @param {Integer} view_id
     * @param {String} view_arch
     * @returns {Deferred}
     */
    _editViewArch: function (view_id, view_arch) {
        core.bus.trigger('clear_cache');
        return this._rpc({
            route: '/web_studio/edit_view_arch',
            params: {
                view_id: view_id,
                view_arch: view_arch,
                context: session.user_context,
            },
        });
    },
    /**
     * @private
     * @override
     */
    _update_control_panel_buttons: function () {
        this._super.apply(this, arguments);
        // the edit button is available in Studio even if not in debug mode
        var is_editable = this.edit_mode_available && !this.in_edit_mode;
        this.$buttons.filter('div.o_edit_mode_available').toggle(is_editable);
    },

    /**
     * @private
     * @override
     */
    _on_iframe_loaded: function () {
        // Check if the iframe has been correctly loaded
        if ($(this.iframe).contents().find('body').is(':empty')) {
            $(this.iframe).replaceWith(QWeb.render('web_studio.report_editor_unavailable'));
            this.$buttons.hide();
        } else {
            this._super.apply(this, arguments);
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @param {OdooEvent} event
     */
    _onEditReport: function (event) {
        var args = event.data.args;
        if (!args) { return; }

        this._editReport(event.data.report, args);
    },
    /**
     * @param {OdooEvent} event
     */
    _onOpenReportForm: function () {
        var options = {
            keep_state: true,
            disable_edition: true,
        };
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: this.res_model,
            res_id: this.res_id,
            views: [[false, 'form']],
            target: 'current',
        }, options);
    },
    /**
     * @param {OdooEvent} event
     */
    _onOpenXMLEditor: function () {
        var self = this;

        this.XMLEditor = new XMLEditor(this, this.view_id, {
            position: 'left',
            doNotLoadLess: true,
        });

        $.when(this.XMLEditor.prependTo(this.$el)).then(function () {
            self.sidebar.$el.detach();
        });
    },
    /**
     * @param {OdooEvent} event
     */
    _onCloseXMLEditor: function () {
        this.XMLEditor.destroy();
        this.sidebar.$el.prependTo(this.$el);
    },
    /**
     * @param {OdooEvent} event
     */
    _onSaveXMLEditor: function (event) {
        var self = this;

        return this._editViewArch(
            event.data.view_id,
            event.data.new_arch
        ).then(function () {
            // reload iframe
            self.$('iframe').attr('src', self.report_url);

            if (event.data.on_success) {
                event.data.on_success();
            }
        });
    },
});

core.action_registry.add('studio_report_editor', ReportEditor);

});
