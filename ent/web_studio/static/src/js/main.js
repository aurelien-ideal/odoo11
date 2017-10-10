odoo.define('web_studio.Main', function (require) {
"use strict";

var core = require('web.core');
var Context = require('web.Context');
var data_manager = require('web.data_manager');
var Dialog = require('web.Dialog');
var dom = require('web.dom');
var form_common = require('web.view_dialogs');
var session = require('web.session');
var Widget = require('web.Widget');

var ActionEditor = require('web_studio.ActionEditor');
var bus = require('web_studio.bus');
var NewViewDialog = require('web_studio.NewViewDialog');
var ViewEditorManager = require('web_studio.ViewEditorManager');

var _t = core._t;
var _lt = core._lt;

var Main = Widget.extend({
    className: 'o_web_studio_client_action',
    error_messages: {
        'wrong_xpath': _lt("This operation caused an error, probably because a xpath was broken"),
        'view_rendering': _lt("The requested change caused an error in the view. It could be because a field was deleted, but still used somewhere else."),
    },
    custom_events: {
        'studio_default_view': '_onSetDefaultView',
        'studio_disable_view': '_onDisableView',
        'studio_edit_view': '_onEditView',
        'studio_new_view': '_onNewView',
        'studio_set_another_view': '_onSetAnotherView',
        'studio_edit_action': '_onEditAction',
        'studio_error': '_onShowError',
    },
    /**
     * @constructor
     * @param {Object} options
     * @param {Object} options.action - action description
     * @param {String} options.active_view
     * @param {Object} options.view_env - view environment
     * @param {Boolean} options.chatter_allowed
     * @param {Object} options.x2mEditorPath
     */
    init: function (parent, context, options) {
        this._super.apply(this, arguments);
        this.action = options.action;
        this.active_view = options.active_view;
        this.view_env = options.view_env;
        this.chatter_allowed = options.chatter_allowed;
        // We set the x2mEditorPath since when we click on the studio breadcrumb
        // a new view_editor_manager is instantiated and then the previous
        // x2mEditorPath is needed to reload the previous view_editor_manager
        // state.
        this.x2mEditorPath = options.x2mEditorPath;
    },
    /**
     * @override
     */
    willStart: function () {
        if (!this.action) {
            return $.Deferred().reject();
        }
        return this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    start: function () {
        var def;
        this.set('title', _t('Studio'));
        if (this.active_view) {
            // directly edit the active view instead of the action
            def = this._editView(this.active_view);
        } else {
            var view_types = this.action.view_mode.split(',');
            this.action_editor = new ActionEditor(this, this.action, view_types);
            def = this.action_editor.appendTo(this.$el);
        }
        return $.when(def, this._super.apply(this, arguments));
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} action
     * @param {String} view_type
     * @param {Object} args
     * @returns {Deferred}
     */
    _addViewType: function (action, view_type, args) {
        var self = this;
        var def = $.Deferred();
        core.bus.trigger('clear_cache');
        this._rpc({
            route: '/web_studio/add_view_type',
            params: {
                action_type: action.type,
                action_id: action.id,
                res_model: action.res_model,
                view_type: view_type,
                args: args,
                context: session.user_context,
            },
        }).then(function (result) {
            if (result !== true) {
                var params = {
                    action: action,
                    callback: function () {
                        self._editAction(action, args).then(function (result) {
                            def.resolve(result);
                        });
                    },
                };
                // TODO find better way to check which view_type is being access
                if (result.indexOf('gantt') !== -1) {
                    params.view_type = 'gantt';
                    new NewViewDialog(self, params).open();
                } else if (result.indexOf('Calendar') !== -1) {
                    params.view_type = 'calendar';
                    new NewViewDialog(self, params).open();
                } else {
                    Dialog.alert(self, result);
                    def.reject();
                }
            } else {
                return self._reloadAction(action.id)
                    .then(def.resolve.bind(def))
                    .fail(def.reject.bind(def));
            }
        });
        return def;
    },
    /**
     * @private
     * @param {Object} action
     * @param {Object} args
     * @returns {Deferred}
     */
    _editAction: function (action, args) {
        var self = this;
        core.bus.trigger('clear_cache');
        return this._rpc({
            route: '/web_studio/edit_action',
            params: {
                action_type: action.type,
                action_id: action.id,
                args: args,
                context: session.user_context,
            },
        }).then(function (result) {
            if (result !== true) {
                Dialog.alert(self, result);
            } else {
                return self._reloadAction(action.id);
            }
        });
    },
    /**
     * @private
     * @param {String} view_type
     */
    _editView: function (view_type) {
        var self = this;
        var options = {};
        var views = this.action.views.slice();

        // search is not in action.view
        options.load_filters = true;
        var searchview_id = this.action.search_view_id && this.action.search_view_id[0];
        views.push([searchview_id || false, 'search']);

        var view = _.find(views, function (el) { return el[1] === view_type; });
        var view_id = view && view[0];

        // the default view needs to be created before `loadViews` or the
        // renderer will not be aware that a new view exists
        var arch_def = this._getStudioViewArch(this.action.res_model, view_type, view_id);
        return arch_def.then(function (studio_view) {
            // add studio in loadViews context to retrieve groups server-side
            var context = new Context(_.extend({}, self.action.context, {studio: true}));
            var view_def = self.loadViews(self.action.res_model, context, views, options);
            return view_def.then(function (fields_views) {
                var view_env = _.defaults({}, self.view_env, {
                    currentId: self.view_env.ids && self.view_env.ids[0],
                });
                var params = {
                    fields_view: fields_views[view_type],
                    view_env: view_env,
                    chatter_allowed: self.chatter_allowed,
                    studio_view_id: studio_view.studio_view_id,
                    studio_view_arch: studio_view.studio_view_arch,
                    x2mEditorPath: self.x2mEditorPath,
                };
                self.view_editor = new ViewEditorManager(self, params);

                var fragment = document.createDocumentFragment();
                return self.view_editor.appendTo(fragment).then(function () {
                    if (self.action_editor) {
                        dom.detach([{widget: self.action_editor}]);
                    }
                    dom.append(self.$el, [fragment], {
                        in_DOM: true,
                        callbacks: [{widget: self.view_editor}],
                    });

                    bus.trigger('edition_mode_entered', view_type);
                });
            });
        });
    },
    /**
     * @private
     * @param {String} model
     * @param {String} view_type
     * @param {Integer} view_id
     * @returns {Deferred}
     */
    _getStudioViewArch: function (model, view_type, view_id) {
        core.bus.trigger('clear_cache');
        return this._rpc({
            route: '/web_studio/get_studio_view_arch',
            params: {
                model: model,
                view_type: view_type,
                view_id: view_id,
                context: session.user_context,
            },
        });
    },
    /**
     * @private
     * @private
     * @param {Integer} action_id
     * @returns {Deferred}
     */
    _reloadAction: function (action_id) {
        return data_manager.load_action(action_id).then(function (new_action) {
            bus.trigger('action_changed', new_action);
            return new_action;
        });
    },
    /**
     * @private
     * @param {String} view_mode
     * @param {Integer} view_id
     * @returns {Deferred}
     */
    _setAnotherView: function (view_mode, view_id) {
        var self = this;
        var def = this._setAnotherViewRPC(this.action.id, view_mode, view_id);
        return def.then(function (result) {
            return self.do_action('action_web_studio_main', {
                action: result,
                disable_edition: true,
            });
        });
    },
    /**
     * @private
     * @param {Integer} action_id
     * @param {String} view_mode
     * @param {Integer} view_id
     * @returns {Deferred}
     */
    _setAnotherViewRPC: function (action_id, view_mode, view_id) {
        var self = this;
        core.bus.trigger('clear_cache');
        return this._rpc({
            route: '/web_studio/set_another_view',
            params: {
                action_id: action_id,
                view_mode: view_mode,
                view_id: view_id,
                context: session.user_context,
            },
        }).then(function () {
            return self._reloadAction(action_id);
        });
    },
    /**
     * @private
     * @param {String} view_mode
     * @returns {Deferred}
     */
    _writeViewMode: function (view_mode, initial_view_mode) {
        var self = this;
        var def = this._editAction(this.action, {view_mode: view_mode});
        return def.then(function (result) {
            if (initial_view_mode) {
                result.initial_view_types = initial_view_mode.split(',');
            }
            return self.do_action('action_web_studio_main', {
                action: result,
                disable_edition: true,
            });
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {OdooEvent} event
     */
    _onDisableView: function (event) {
        var view_type = event.data.view_type;
        var view_mode = _.without(this.action.view_mode.split(','), view_type);

        this._writeViewMode(view_mode.toString());
    },
    /**
     * @private
     * @param {OdooEvent} event
     */
    _onEditAction: function (event) {
        var self = this;

        var args = event.data.args;
        if (!args) { return; }

        this._editAction(this.action, args).then(function (result) {
            self.action = result;
        });
    },
    /**
     * @private
     * @param {OdooEvent} event
     */
    _onEditView: function (event) {
        var view_type = event.data.view_type;
        this._editView(view_type);
    },
    /**
     * @private
     * @param {OdooEvent} event
     */
    _onNewView: function (event) {
        var self = this;
        var view_type = event.data.view_type;
        var view_mode = this.action.view_mode + ',' + view_type;
        var def = this._addViewType(this.action, view_type, {
            view_mode: view_mode,
        });
        def.then(function (result) {
            self.do_action('action_web_studio_main', {
                action: result,
                active_view: view_type,
                disable_edition: true,
            });
        });
    },
    /**
     * @private
     * @param {OdooEvent} event
     */
    _onSetAnotherView: function (event) {
        var self = this;
        var view_type = event.data.view_type;

        new form_common.SelectCreateDialog(this, {
            res_model: 'ir.ui.view',
            title: _t('Select a view'),
            disable_multiple_selection: true,
            no_create: true,
            domain: [
                ['type', '=', view_type],
                ['mode', '=', 'primary'],
                ['model', '=', this.action.res_model],
            ],
            on_selected: function (records) {
                self._setAnotherView(view_type, records[0].id);
            }
        }).open();
    },
    /**
     * @private
     * @param {OdooEvent} event
     */
    _onSetDefaultView: function (event) {
        var view_type = event.data.view_type;
        var view_mode = _.without(this.action.view_mode.split(','), view_type);
        view_mode.unshift(view_type);
        view_mode = view_mode.toString();

        this._writeViewMode(view_mode, this.action.view_mode);
    },
    /**
     * @private
     * @param {OdooEvent} event
     */
    _onShowError: function (event) {
        this.do_warn(_t("Error"), this.error_messages[event.data.error]);
    },
});

core.action_registry.add('action_web_studio_main', Main);

});
