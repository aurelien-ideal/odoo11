odoo.define('web_studio.studio_report_kanban', function (require) {
"use strict";

var core = require('web.core');
var Dialog = require('web.Dialog');
var KanbanController = require('web.KanbanController');
var KanbanView = require('web.KanbanView');
var session = require('web.session');
var view_registry = require('web.view_registry');

var _t = core._t;

var StudioReportKanbanController = KanbanController.extend({

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Do not add a record but open the dialog.
     *
     * @private
     * @override
     */
    _onButtonNew: function () {
        var model = this.initialState.context.search_default_model;
        new NewReportDialog(this, model).open();
    },
    /**
     * Do not open the form view but open the Report Editor action.
     *
     * @param {OdooEvent} event
     * @param {Integer} [event.data.res_id] The record res ID (if it directly
     *   comes from the server)
     * @param {number} [event.data.id] The local model ID for the record to be
     *   opened
     * @private
     * @override
     */
    _onOpenRecord: function (event) {
        event.stopPropagation();
        var self = this;
        var res_id = event.data.res_id;
        if (!res_id) {
            res_id = this.model.get(event.data.id, {raw: true}).res_id;
        }
        this._rpc({
                model: 'ir.actions.report',
                method: 'studio_edit',
                args: [res_id],
            })
            .then(function(action) {
                if (action.active_ids.length) {
                    self.do_action(action, {
                        keep_state: true,
                        disable_edition: true,
                    });
                } else {
                    new Dialog(this, {
                        size: 'medium',
                        title: _t('No record to display.'),
                        $content: $('<div>', {
                            text: _t("First, quit Odoo Studio to create a new entity. Then, open Odoo Studio to create or edit reports."),
                        }),
                    }).open();
                }
            });
    },
});

var NewReportDialog = Dialog.extend({
    template: 'web_studio.NewReportDialog',
    events: {
        'click .o_web_studio_report_template_item': '_onReportTemplate',
    },
    /**
     * @constructor
     * @param {Widget} parent
     * @param {String} res_model
     */
    init: function (parent, res_model) {
        this.res_model = res_model;
        var options = {
            title: _t("Select a report template"),
            size: 'medium',
            buttons: [],
        };

        this.templates = [{
            name: 'report_business',
            label: _t("Preview Business Document"),
            description: _t("(e.g. Sales order)"),
        }, {
            name: 'report_blank',
            label: _t("Preview Blank Document"),
            description: _t("(empty report with footer and header)"),
        }];

        this._super(parent, options);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {String} model_name
     * @param {String} template_name
     * @returns {Deferred}
     */
    _createNewReport: function (model_name, template_name) {
        return this._rpc({
            route: '/web_studio/create_new_report',
            params: {
                model_name: model_name,
                template_name: template_name,
                context: session.user_context,
            },
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Create a new report.
     *
     * @private
     * @param {Event} event
     */
    _onReportTemplate: function (event) {
        var self = this;
        var template_name = $(event.currentTarget).data('template');
        this._createNewReport(this.res_model, template_name).then(function (result) {
            self.trigger_up('open_record', {res_id: result.id});
            self.close();
        });
    },
});

var StudioReportKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: StudioReportKanbanController,
    }),
});

view_registry.add('studio_report_kanban', StudioReportKanbanView);

return StudioReportKanbanView;

});
