odoo.define('web_studio.ActionManager', function (require) {
"use strict";

var ActionManager = require('web.ActionManager');

ActionManager.include({

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Avoid clearing action with the `keep_alive` key.
     *
     * @override
     * @param {Object} action_stack
     */
    clear_action_stack: function (action_stack) {
        action_stack = action_stack && _.reject(action_stack, {keep_alive: true});
        this._super(action_stack);
    },
    /**
     * Avoid pushing the state if `keep_state` is in `action_descr`.
     * This is used in Studio to keep a reloadable URL despite another action
     * (ex: intern navigation inside Studio) has been pushed.
     *
     * @override
     */
    do_push_state: function () {
        if (this.inner_action) {
            var inner_action_descr = this.inner_action.get_action_descr();
            if (inner_action_descr.keep_state) {
                return;
            }
        }
        this._super.apply(this, arguments);
    },
    /**
     * Put keep state in the `action_descr` if it is in options.
     * We want to have it in the `action_descr` (because it's the only
     * parameter of `do_push_state`) but it's not always possible
     * (ex: action described in XML).
     *
     * @override
     * @param {Object} action
     * @param {Object} options
     */
    do_action: function (action, options) {
        if (_.isObject(action) && options && 'keep_state' in options) {
            action.keep_state = options.keep_state;
        }
        return this._super.apply(this, arguments);
    },
    /**
     * Restore the action stack.
     *
     * @param {Object} action_stack
     * @returns {Deferred}
     */
    restoreActionStack: function (action_stack) {
        var self = this;
        var def;
        var to_destroy = this.action_stack;
        var last_action = _.last(action_stack);
        this.action_stack = action_stack;

        if (last_action && last_action.action_descr.id) {
            var view_type = last_action.get_active_view && last_action.get_active_view();
            var res_id = parseInt($.deparam(window.location.hash.slice(1)).id);

            // The action could have been modified (name, view_ids, etc.)
            // so we need to use do_action to reload it.
            def = this.do_action(last_action.action_descr.id, {
                view_type: view_type,
                replace_last_action: true,
                res_id: res_id,
                additional_context: last_action.action_descr.context,
            });
        } else {
            def = $.Deferred().reject();
        }
        return def.fail(function () {
            self.clear_action_stack();
            self.trigger_up('show_app_switcher');
        }).always(this.clear_action_stack.bind(this, to_destroy));
    },
});

});
