odoo.define('web_studio.AppSwitcher', function (require) {
"use strict";

var core = require('web.core');
var session = require('web.session');
var WebClient = require('web.WebClient');
var web_client = require('web.web_client');
var AppSwitcher = require('web_enterprise.AppSwitcher');

var bus = require('web_studio.bus');

var QWeb = core.qweb;

/*
 * Notice:
 *  some features (like seeing the appswitcher background) are available
 *  even the user is not a system user, this is why there are two different
 *  includes in this file.
 */

AppSwitcher.include({
    /**
     * @override
     */
    start: function () {
        this.setBackgroundImage();
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     * @param {Object} menu_data
     */
    process_menu_data: function (menu_data) {
        this.has_custom_background = menu_data.background_image;
        return this._super.apply(this, arguments);
    },
    /**
     * Put the appswitcher background as the cover of current `$el`.
     */
    setBackgroundImage: function () {
        if (this.has_custom_background) {
            var url = session.url('/web/image', {
                model: 'res.company',
                id: session.company_id,
                field: 'background_image',
            });
            this.$el.css({
                "background-image": "url(" + url + ")",
                "background-size": "cover",
            });
        }
    },
});

WebClient.include({
    /**
     * Adds a class on the webclient on top of the o_app_switcher_background
     * class to inform that the appswitcher is customized.
     *
     * @override
     */
    toggle_app_switcher: function (display) {
        this._super.apply(this, arguments);
        this.$el.toggleClass('o_app_switcher_background_custom', display && !!this.menu_data.background_image);
    },
});

if (!session.is_system) {
    return;
}

AppSwitcher.include({
    events: _.extend(AppSwitcher.prototype.events, {
        'click .o_web_studio_new_app': '_onNewApp',
    }),
    /**
     * @override
     */
    start: function () {
        bus.on('studio_toggled', this, this.toggleStudioMode);
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @param {Boolean} display
     */
    toggleStudioMode: function (display) {
        this.in_studio_mode = display;
        if (!this.in_DOM) {
            return;
        }
        if (display) {
            this.on_detach_callback();  // de-bind hanlders on appswitcher
            this.in_DOM = true;  // avoid effect of on_detach_callback
            this.renderNewApp();
        } else {
            this.$new_app.remove();
            this.on_attach_callback();
        }
    },
    /**
     * Add the 'New App' icon.
     */
    renderNewApp: function () {
        this.state = this.get_initial_state();
        this.render();
        this.$new_app = $(QWeb.render('web_studio.AppCreator.NewApp'));
        this.$new_app.appendTo(this.$('.o_apps'));
    },
    /**
     * @override
     */
    on_attach_callback: function () {
        this.in_DOM = true;
        if (this.in_studio_mode) {
            this.renderNewApp();
        } else {
            this._super.apply(this, arguments);
        }
    },
    /**
     * @override
     */
    on_detach_callback: function () {
        this._super.apply(this, arguments);
        this.in_DOM = false;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} event
     */
    _onNewApp: function (event) {
        event.preventDefault();
        web_client.openStudio('app_creator').then(function () {
            core.bus.trigger('toggle_mode', true, false);
        });
    },
});

});
