odoo.define('web_studio.Menu', function (require) {
"use strict";

var core = require('web.core');
var data_manager = require('web.data_manager');
var framework = require('web.framework');
var Menu = require('web_enterprise.Menu');
var session = require('web.session');

var bus = require('web_studio.bus');
var EditMenu = require('web_studio.EditMenu');
var SubMenu = require('web_studio.SubMenu');

var qweb = core.qweb;
var _t = core._t;

Menu.include({
    events: _.extend({}, Menu.prototype.events, {
        'click .o_web_studio_change_background': '_onChangeBackground',
        'click .o_web_studio_export': '_onExport',
        'click .o_web_studio_import': '_onImport',
    }),
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        bus.on('studio_toggled', this, this.switch_studio_mode.bind(this));
        this.widget = "image";
        this.company_id = session.company_id;
        this.fileupload_id = _.uniqueId('o_fileupload');
        $(window).on(this.fileupload_id, this._onBackgroundLoaded.bind(this));
    },
    /**
     * @override
     */
    destroy: function () {
        $(window).off(this.fileupload_id);
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Modifies the menu according to the Studio mode (black navbar,
     * leave and notes buttons, etc.)
     * @param {String} mode - 'main'/'app_creator' for Studio or false
     * @param {Object} studio_info - mandatory if mode
     *        - multi_lang
     *        - dbuuid
     * @param {Object} action - edited action, mandatory if mode = 'main'
     * @param {Object} active_view - mandatory if mode = 'main'
     */
    switch_studio_mode: function (mode, studio_info, action, active_view) {
        var self = this;
        var old_mode = this.studio_mode;
        if (old_mode === mode) {
            return;
        }

        this.studio_mode = mode;
        this._clean();

        if (mode) {
            var $main_navbar = this.$('.o_main_navbar');
            if (!old_mode) {
                this.$detached_systray = this.$('.o_menu_systray').detach();
            }

            if (mode === 'main') {
                var options = { multi_lang: studio_info.multi_lang };
                this.studio_menu = new SubMenu(this, action, active_view, options);
                this.studio_menu.insertAfter($main_navbar);

                if (this.current_primary_menu) {
                    this.edit_menu = new EditMenu.MenuItem(this, this.menu_data, this.current_primary_menu);
                    this.edit_menu.appendTo($main_navbar.find('.o_menu_sections'));
                }
            } else {
                // In app switcher
                this.$app_switcher_menu = $(qweb.render('web_studio.AppSwitcherMenu', {
                    widget: this,
                }));
                this.$app_switcher_menu.appendTo($main_navbar);
            }

            // Leave button
            this.$leave_button = $('<div>')
                .addClass('o_web_studio_leave')
                .append($('<a>', {
                    href: '#',
                    class: 'btn btn-primary',
                    text: _t("Close"),
                }))
                .click(function (event) {
                    event.preventDefault();
                    if (!$(this).hasClass('o_disabled')) {
                        self.trigger_up('click_studio_mode');
                    }
                    $(this).addClass('o_disabled');
                });
            this.$leave_button.appendTo($main_navbar);

            // Notes link
            this.$notes = $('<div>')
                .addClass('o_web_studio_notes')
                .append($('<a>', {
                    href: 'http://pad.odoo.com/p/customization-' + studio_info.dbuuid,
                    target: '_blank',
                    text: _t("Notes"),
                }));
            this.$notes.appendTo($main_navbar);
        } else {
            this.$detached_systray.prependTo('.o_main_navbar');
        }
    },
    /**
     * @override
     */
    toggle_mode: function (appswitcher) {
        this._super.apply(this, arguments);

        if (!appswitcher && this.$app_switcher_menu) {
            this.$app_switcher_menu.remove();
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _clean: function () {
        if (this.edit_menu) {
            this.edit_menu.destroy();
            this.edit_menu = undefined;
        }
        if (this.studio_menu) {
            this.studio_menu.destroy();
            this.studio_menu = undefined;
        }
        if (this.$notes) {
            this.$notes.remove();
            this.$nodes = undefined;
        }
        if (this.$leave_button) {
            this.$leave_button.remove();
            this.$leave_button = undefined;
        }
        if (this.$app_switcher_menu) {
            this.$app_switcher_menu.remove();
            this.$app_switcher_menu = undefined;
        }
    },
    /**
     * @private
     * @param {Integer} attachment_id
     * @returns {Deferred}
     */
    _setBackgroundImage: function (attachment_id) {
        return this._rpc({
            route: '/web_studio/set_background_image',
            params: {
                attachment_id: attachment_id,
                context: session.user_context,
            },
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @param {Event} event
     * @param {Object} result
     */
    _onBackgroundLoaded: function (event, result) {
        if (result.error || !result.id ) {
            this.do_warn(result.error);
        } else {
            framework.blockUI();
            this._setBackgroundImage(result.id)
                .then(function () {
                    window.location.reload();
                }).fail(function () {
                    framework.unblockUI();
                });

        }
    },
    /**
     * @private
     */
    _onChangeBackground: function () {
        var self = this;
        this.$('input.o_input_file').on('change', function () {
            self.$('form.o_form_binary_form').submit();
        });
        this.$('input.o_input_file').click();
    },
    /**
     * Export all customizations done by Studio in a zip file containing Odoo
     * modules.
     *
     * @param {Event} event
     */
    _onExport: function (event) {
        event.preventDefault();
        var $export = $(event.currentTarget);
        // disable the export button while it is exporting
        $export.addClass('o_disabled');
        session.get_file({
            url: '/web_studio/export',
            // re-enable export
            complete: $export.removeClass.bind($export, 'o_disabled'),
        });
    },
    /**
     * Open a dialog allowing to import new modules
     * (e.g. exported customizations).
     *
     * @param {Event} event
     */
    _onImport: function (event) {
        event.preventDefault();
        var self = this;
        this.do_action({
            name: 'Import modules',
            res_model: 'base.import.module',
            views: [[false, 'form']],
            type: 'ir.actions.act_window',
            target: 'new',
            context: {
                dialog_size: 'medium',
            },
        }, {
            on_close: function () {
                core.bus.trigger('clear_cache'); // invalidate cache
                self.trigger_up('reload_menu_data'); // reload menus
            },
        });
    },
});

});
