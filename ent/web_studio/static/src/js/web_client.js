odoo.define('web_studio.WebClient', function (require) {
"use strict";

var ActionManager = require('web.ActionManager');
var core = require('web.core');
var session = require('web.session');
var WebClient = require('web.WebClient');

var SystrayItem = require('web_studio.SystrayItem');
var bus = require('web_studio.bus');

var _t = core._t;

if (!session.is_system) {
    // Studio is only available for the Administrator, so display a notification
    // if another user tries to access it through the url
    WebClient.include({
        show_application: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                var qs = $.deparam.querystring();
                if (qs.studio !== undefined) {
                    var msg = _t("Studio is only available for the Administrator");
                    self.notification_manager.notify(_t("Access error"), msg, true);
                    // Remove studio from the url, without reloading
                    delete qs.studio;
                    var l = window.location;
                    var url = l.protocol + "//" + l.host + l.pathname + '?' + $.param(qs) + l.hash;
                    window.history.pushState({ path:url }, '', url);
                }
            });
        },
    });

    return;
}

WebClient.include({
    custom_events: _.extend({}, WebClient.prototype.custom_events, {
        'click_studio_mode': '_onStudioMode',
        'new_app_created': '_onNewAppCreated',
        'reload_menu_data': '_onReloadMenuData',
    }),
    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        this.studio_mode = false;
        this.studio_info_def = null;
        this.studio_action_manager = null;

        bus.on('studio_toggled', this, function (mode) {
            this.studio_mode = mode;
            this._updateContext(!!mode);
            this.$el.toggleClass('o_in_studio', !!mode);
        });
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @returns {Deferred}
     */
    closeStudio: function () {
        this.edited_action = undefined;
        this.studio_mode = false;

        var action = this.action_manager.get_inner_action();
        var action_desc = action && action.action_descr || null;
        var def = $.Deferred();
        if (this.app_switcher_displayed) {
            this.action_manager.clear_action_stack();
            this.menu.toggle_mode(true, false);
            def.resolve();
        } else if (action_desc.tag === 'action_web_studio_app_creator') {
            // we are not in the app_switcher but we want to display it
            this.action_manager.clear_action_stack();
            this.toggle_app_switcher(true);
            def.resolve();
        } else {
            def = this.action_manager.restoreActionStack(this.studio_action_manager.action_stack);
        }
        return def;
    },
    /**
     * @override
     */
    do_action: function (action, options) {

        if (this.studio_mode === 'main' && action.target === 'new') {
            // Wizards in the app creator can be opened (ex: Import wizard)
            // TODO: what if we modify target = 'curent' to modify it?
            this.do_warn("Studio", _t("Wizards are not editable with Studio."));
            return $.Deferred().reject();
        }

        // the option `disable_edition` can be used to tell the webclient that
        // the action is not a navigation we want to navigation in Studio with, but
        // it's an action we want to open normally (because it is used by Studio).
        if (this.studio_mode && !options.disable_edition) {
            // we are navigating inside Studio so the studio action manager is used
            return this.studio_action_manager.do_action.apply(this, arguments);
        }

        if (this.studio_mode === 'main') {
            // these are options used by Studio main action
            options = options || {};
            options.view_env = this.edited_action.widget.env;
            options.chatter_allowed = this.studio_chatter_allowed;
        }

        return this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    do_push_state: function (state) {
        if (this.studio_mode && typeof(state.action) === 'string' && state.action.indexOf('action_web_studio_') !== -1) {
            return; // keep edited action in url when we enter in studio to allow restoring it on refresh
        }
        return this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    current_action_updated: function (action) {
        this._super.apply(this, arguments);

        // the method is overwritten by the debug manager to update to null if the appswitcher is
        // displayed, but we don't need this in Studio ; we only need to update the action if there is one.
        if (action && !action.action_descr.keep_state && action.action_descr.tag !== 'action_web_studio_main') {
            this._updateStudioSystray(this._isStudioEditable(action));
            this.edited_action = action;
        }
    },
    /**
     * @param {String} mode
     * @param {Object} options
     * @returns {Deferred}
     */
    openStudio: function (mode, options) {
        options = options || {};
        var self = this;
        var action = options.action;
        var action_options = {
            clear_breadcrumbs: true,
            disable_edition: true,
        };
        var defs = [];
        this.studio_mode = mode;
        this.edited_action = action;
        if (action) {
            defs.push(session.rpc('/web_studio/chatter_allowed', {
                model: action.action_descr.res_model,
            }));
            // we are editing an action, not in app creator mode
            if (options.active_view) {
                action_options.active_view = options.active_view;
                defs.push(action.widget.switch_mode(options.active_view));
            } else {
                action_options.active_view = action.get_active_view();
            }
            action_options.action = action.action_descr;
        }
        return $.when.apply($, defs).then(function (chatter_allowed) {
            self.studio_chatter_allowed = chatter_allowed;
            // grep: action_web_studio_app_creator, action_web_studio_main
            return self.do_action('action_web_studio_' + mode, action_options);
        });
    },
    /**
     * @override
     */
    show_application: function () {
        var self = this;
        var _super = this._super.bind(this, arguments);
        var qs = $.deparam.querystring();
        var studio_mode = _.contains(['main', 'app_creator'], qs.studio) ? qs.studio : false;
        if (!studio_mode) {
            return this._super.apply(this, arguments);
        }
        this._updateContext(true);
        return this._loadStudioInfo().then(function (studio_info) {
            self.studio_info = studio_info;
            return _super().then(function () {
                var action_descr;
                var active_view;
                var defs = [];
                defs.push(self._setStudioActionManager());
                if (studio_mode === 'main') {
                    var action = self.action_manager.get_inner_action();
                    if (action) {
                        action_descr = action.action_descr;
                        active_view = action.get_active_view();
                        defs.push(self.openStudio('main', { action: action }));
                    } else {
                        return $.when();
                    }
                }
                return $.when.apply($, defs).then(function () {
                    bus.trigger('studio_toggled', studio_mode, studio_info, action_descr, active_view);
                });
            });
        });
    },
    /**
     * Clicking on a menu/app while being in Studio mode pushed the action
     * in another action manager and then open studio with this new action.
     * This allows us to get everything without modifying the dom.
     *
     * @override
     */
    on_menu_clicked: function () {
        if (this.studio_mode) {
            var last_action_stack = this.studio_action_manager.action_stack;
            var last_state = $.bbq.getState(true);
            return this._super.apply(this, arguments)
                .then(this._openNavigatedActionInStudio.bind(this))
                .fail(this._restoreStudioState.bind(this, last_action_stack, last_state));
        }
        return this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    on_app_clicked: function () {
        if (this.studio_mode) {
            var last_action_stack = this.studio_action_manager.action_stack;
            var last_state = $.bbq.getState(true);
            return this._super.apply(this, arguments)
                .fail(this._restoreStudioState.bind(this, last_action_stack, last_state));
        }
        return this._super.apply(this, arguments);
    },
    /**
     * @override
     * @param {Boolean} display
     */
    toggle_app_switcher: function (display) {
        if (display) {
            // the Studio icon is enabled in the appswitcher (for the app creator)
            this._updateStudioSystray(true);
        }

        if (this.studio_mode) {
            if (display) {
                bus.trigger('studio_toggled', 'app_creator', this.studio_info);
            } else {
                if (this.edited_action.action_descr.tag === 'action_web_studio_app_creator') {
                    // special case for the app_creator, which stays in app_creator mode
                    bus.trigger('studio_toggled', 'app_creator', this.studio_info);
                } else {
                    bus.trigger('studio_toggled', 'main', this.studio_info, this.edited_action.action_descr, this.edited_action.get_active_view());
                }
            }
        }

        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _destroyStudioActionManager: function () {
        this.studio_action_manager.destroy();
        this.studio_action_manager = null;
    },
    /**
     * Studio is disabled by default in systray
     * Add conditions here to enable it
     */
    _isStudioEditable: function (action) {
        if (action && action.action_descr.xml_id) {
            var descr = action.action_descr;
            if (descr.type === 'ir.actions.act_window') {
                // we don't want to edit Settings as it is a special case of form view
                // this is a heuristic to determine if the action is Settings
                if (descr.res_model && descr.res_model.indexOf('settings') === -1) {
                    return true;
                }
            }
        }
        return false;
    },
    /**
     * Performs the initial RPC for studio to get the global useful information.
     *
     * @private
     * @returns {Deferred}
     */
    _loadStudioInfo: function () {
        if (!this.studio_info_def) {
            this.studio_info_def = session.rpc('/web_studio/init');
        }
        return this.studio_info_def;
    },
    /**
     * @override
     */
    _on_app_clicked_done: function (ev) {
        if (this.studio_mode) {
            core.bus.trigger('change_menu_section', ev.data.menu_id);
            // load the action before toggle the appswitcher
            return this._openNavigatedActionInStudio(ev.data.options)
                .then(this.toggle_app_switcher.bind(this, false));
        } else {
            return this._super.apply(this, arguments);
        }
    },
    /**
     * @private
     * @param {Object} options
     * @returns {Deferred}
     */
    _openNavigatedActionInStudio: function (options) {
        var action = this.studio_action_manager.get_inner_action();
        if (!this._isStudioEditable(action)) {
            this.do_warn("Studio", _t("This action is not editable by Studio"));
            return $.Deferred().reject();
        }
        bus.trigger('action_changed', action.action_descr);
        return this.openStudio('main', _.extend(options || {}, { action: action }));
    },
    /**
     * Restore the Studio action manager to a previous state.
     * This is useful when a do_action has been done on an action that couldn't
     * be edited by Studio ; in this case, we restore it.
     *
     * @private
     * @param {Array} action_stack
     * @param {Object} state
     */
    _restoreStudioState: function (action_stack, state) {
        var last_action = _.last(action_stack);
        this.studio_action_manager.clear_action_stack();
        this.studio_action_manager.action_stack = action_stack;
        this.studio_action_manager.inner_action = last_action;
        this.studio_action_manager.inner_widget = last_action && last_action.widget;
        $.bbq.pushState(state, 2);
    },
    /**
     * Create a new action manager that will be used to navigate in Studio.
     *
     * @private
     * @returns {Deferred}
     */
    _setStudioActionManager: function () {
        var fragment = document.createDocumentFragment();
        this.studio_action_manager = new ActionManager(this, {webclient: this});

        // Save the current action stack to restore it when leaving studio.
        // These actions cannot be destroyed (hence keep_alive) because when
        // we leave Studio and restore the action stack, these action are re-used.
        this.studio_action_manager.action_stack = this.action_manager.action_stack;
        _.each(this.action_manager.action_stack, function (action) {
            action.keep_alive = true;
        });

        // TODO after new views: this action manager will not be appended
        // inside the dom and we don't need the views to be displayed so switch_mode
        // should be monkey-patched to avoid RPCs.

        return this.studio_action_manager.appendTo(fragment);
    },
    /**
     * @private
     * @param {Boolean} in_studio
     */
    _updateContext: function (in_studio) {
        if (in_studio) {
            // Write in user_context that we are in Studio
            // This is used server-side to flag with Studio the ir.model.data of customizations
            session.user_context.studio = 1;
        } else {
            delete session.user_context.studio;
        }
    },
    /**
     * @private
     * @param {Boolean} show
     */
    _updateStudioSystray: function (show) {
        var systray_item = _.find(this.menu.systray_menu.widgets, function (item) {
            return item instanceof SystrayItem;
        });
        if (show) {
            systray_item.enable();
        } else {
            systray_item.disable();
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onNewAppCreated: function (ev) {
        var self = this;
        this.instanciate_menu_widgets().then(function () {
            self.on_app_clicked({
                data: {
                    menu_id: ev.data.menu_id,
                    action_id: ev.data.action_id,
                    options: {
                        active_view: 'form',
                    }
                }
            });
            self.menu.toggle_mode(false);  // display app switcher button
        });
    },
    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onReloadMenuData: function (ev) {
        var self = this;

        var current_primary_menu = this.menu.current_primary_menu;

        var action = this.edited_action;
        var action_desc = action && action.action_descr || null;
        var active_view = action && action.get_active_view();
        $.when(this.studio_mode && this._loadStudioInfo()).then(function (studio_info) {
            self.instanciate_menu_widgets().then(function () {
                // reload previous state
                self.menu.toggle_mode(self.app_switcher_displayed);
                self.menu.change_menu_section(current_primary_menu); // entering the current menu
                if (self.app_switcher_displayed) {
                    self.append_app_switcher();
                }

                self.menu.switch_studio_mode(self.studio_mode, studio_info, action_desc, active_view);
                self._updateStudioSystray(!!self.studio_mode);
                self.app_switcher.toggleStudioMode(!!self.studio_mode);

                if (ev && ev.data.keep_open) {
                    self.menu.edit_menu.editMenu();
                }
                if (ev && ev.data.def) {
                    ev.data.def.resolve();
                }
            });
        });
    },
    /**
     * @private
     */
    _onStudioMode: function () {
        var self = this;
        this.studio_mode = !this.studio_mode && (this.app_switcher_displayed ? 'app_creator' : 'main');
        var action = this.action_manager.get_inner_action();
        var action_desc = action && action.action_descr || null;
        var active_view = action && action.get_active_view();

        this._updateContext(!!this.studio_mode);

        var defs = [];
        if (this.studio_mode) {
            defs.push(this._loadStudioInfo());
            defs.push(this._setStudioActionManager());

            if (this.app_switcher_displayed) {
                this.action_manager.clear_action_stack();
                this.menu.toggle_mode(true, false);
            } else {
                defs.push(this.openStudio('main', { action: action}));
            }
        } else {
            var def = $.Deferred();
            defs.push(def);
            this.closeStudio().always(function () {
                self._destroyStudioActionManager();
                def.resolve();
            });
        }
        return $.when.apply($, defs).then(function (studio_info) {
            self.studio_info = studio_info;
            bus.trigger('studio_toggled', self.studio_mode, studio_info, action_desc, active_view);
            if (self.studio_mode) {
                self._updateStudioSystray(true);
            }
            if (!self.studio_mode && self.app_switcher_displayed) {
                self.trigger_up('show_app_switcher');
            }
        });
    },

});

});
