odoo.define('web_studio.SubMenu', function (require) {
"use strict";

var ajax = require('web.ajax');
var core = require('web.core');
var Widget = require('web.Widget');

var bus = require('web_studio.bus');

var _t = core._t;

var SubMenu = Widget.extend({
    template: 'web_studio.Menu',
    events: {
        'click .o_menu_sections > li > a': '_onMenu',
        'click .o_web_studio_undo': '_onUndo',
        'click .o_web_studio_redo': '_onRedo',
        'click .o_menu_sections .o_web_studio_views_icons > a': '_onIcon',
    },
    /**
     * @constructor
     * @param {Widget} parent
     * @param {Object} action
     * @param {String} active_view
     * @param {Object} options
     */
    init: function (parent, action, active_view, options) {
        var self = this;

        this._super.apply(this, arguments);
        this.action = action;
        this.active_view_types = this.action.view_mode.split(',');
        this.studio_actions = [{action: 'action_web_studio_main', title: 'Views'}];
        this.multi_lang = options.multi_lang;
        if (active_view) {
            var bc_options = {
                action: 'action_web_studio_main',
                active_view: active_view,
                title: active_view.charAt(0).toUpperCase() + active_view.slice(1),
            };
            this._addAction(bc_options);
        }
        bus.on('action_changed', this, this._onActionChanged.bind(this));

        bus.on('undo_available', this, this._onToggleUndo.bind(this, true));
        bus.on('undo_not_available', this, this._onToggleUndo.bind(this, false));
        bus.on('redo_available', this, this._onToggleRedo.bind(this, true));
        bus.on('redo_not_available', this, this._onToggleRedo.bind(this, false));

        bus.on('edition_mode_entered', this, function (view_type) {
            if (self.studio_actions.length === 1) {
                bc_options = {
                    action: 'action_web_studio_main',
                    active_view: view_type,
                    title: view_type.charAt(0).toUpperCase() + view_type.slice(1),
                };
                self._addAction(bc_options);
            }
        });
        bus.on('edition_x2m_entered', this, function (subview_type, x2mEditorPath) {
            bc_options = {
                action: 'action_web_studio_main',
                active_view: subview_type,
                x2mEditorPath: x2mEditorPath.slice(),
                title: _t('Subview ') + subview_type,
            };
            self._addAction(bc_options);
        });
    },
    /**
     * @override
     */
    renderElement: function() {
        this._super.apply(this, arguments);
        this._renderBreadcrumb();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} options
     */
    _addAction: function (options) {
        this.$('.o_menu_sections li a.active').removeClass('active');
        this.studio_actions.push(options);
        this.renderElement();
    },
    /**
     * @private
     */
    _renderBreadcrumb: function () {
        var self = this;
        var $breadcrumb = $('<ol>').addClass('breadcrumb');
        _.each(this.studio_actions, function (bc, index) {
            $breadcrumb.append(
                self._renderBreadcrumbsLi(bc, index, self.studio_actions.length)
            );
        });
        this.$('.o_web_studio_breadcrumb')
            .empty()
            .append($breadcrumb);
    },
    /**
     * @private
     * @param {TODO} bc
     * @param {Integer} index
     * @param {Integer} length
     * @returns {JQuery}
     */
    _renderBreadcrumbsLi: function (bc, index, length) {
        var self = this;
        var is_last = (index === length-1);
        var li_content = bc.title && _.escape(bc.title.trim());
        var $bc = $('<li>')
            .append(li_content)
            .toggleClass('active', is_last);
        if (!is_last) {
            $bc.click(function () {
                var options = {
                    action: self.action,
                    clear_breadcrumbs: true,
                    disable_edition: true,
                    index: index,
                };
                if (bc.active_view) {
                    options.active_view = bc.active_view;
                }
                if (bc.x2mEditorPath) {
                    options.x2mEditorPath = bc.x2mEditorPath.slice();
                }
                self._replaceAction(bc.action, bc.title, options);
            });
            $bc.toggleClass('o_back_button');
        }
        return $bc;
    },
    /**
     * Replace the current action and render the breadcrumb.
     *
     * @param {Object} action
     * @param {String} title
     * @param {Object} options
     */
    _replaceAction: function (action, title, options) {
        if (options.active_view) {
            if (options.index > 1) {
                this.studio_actions.length = options.index + 1;
            } else {
                this.studio_actions = [
                    {action: 'action_web_studio_main', title: _t('Views')},
                    {action: action, title: title, active_view: options.active_view},
                ];
            }
        } else {
            this.studio_actions = [{action: action, title: title}];
        }
        this.do_action(action, options);
        this.renderElement();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} new_action
     */
    _onActionChanged: function (new_action) {
        this.action = new_action;
        this.active_view_types = this.action.view_mode.split(',');
        this.renderElement();
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onIcon: function (ev) {
        ev.preventDefault();
        var view_name = $(ev.currentTarget).data('name');
        return this._replaceAction('action_web_studio_main', view_name, {
            action: this.action,
            active_view: view_name,
            clear_breadcrumbs: true,
            disable_edition: true,
        });
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onMenu: function (ev) {
        var $menu = $(ev.currentTarget);
        if (!$menu.data('name')) { return; }

        // make the primary menu active
        this.$('.active').removeClass('active');
        $menu.addClass('active');

        // do the corresponding action
        var title = $menu.text();
        var name = $menu.data('name');
        if (name === 'views') {
            this._replaceAction('action_web_studio_main', title, {
                action: this.action,
                clear_breadcrumbs: true,
                disable_edition: true,
            });
        } else if (_.contains(['automations', 'reports', 'acl', 'filters'], name)) {
            var self = this;
            ajax.jsonRpc('/web_studio/get_studio_action', 'call', {
                action_name: name,
                model: this.action.res_model,
                view_id: this.action.view_id[0],
            }).then(function (result) {
                self._replaceAction(result, title, {
                    clear_breadcrumbs: true,
                    disable_edition: true,
                    keep_state: true,
                });
            });
        }
    },
    /**
     * @private
     */
    _onRedo: function () {
        bus.trigger('redo_clicked');
    },
    /**
     * @private
     * @param {Boolean} display
     */
    _onToggleUndo: function (display) {
        this.$('.o_web_studio_undo').toggleClass('o_web_studio_active', display);
    },
    /**
     * @private
     * @param {Boolean} display
     */
    _onToggleRedo: function (display) {
        this.$('.o_web_studio_redo').toggleClass('o_web_studio_active', display);
    },
    /**
     * @private
     */
    _onUndo: function () {
        bus.trigger('undo_clicked');
    },
});

return SubMenu;

});
