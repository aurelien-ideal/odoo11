odoo.define('web_enterprise.FormView', function (require) {
"use strict";

/**
 * The purpose of this file is to make the FormView use a special FormRenderer
 * in mobile, implementing some tweaks to improve the UX in mobile.
 */

var config = require('web.config');
var FormRenderer = require('web.FormRenderer');
var FormView = require('web.FormView');
var MobileFormRenderer = require('web_enterprise.MobileFormRenderer');

FormView.include({
    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Overrides to select the MobileFormRenderer in mobile instead of the
     * FormRenderer.
     *
     * @override
     */
    getRenderer: function () {
        this.config.Renderer = config.device.isMobile ? MobileFormRenderer : FormRenderer;
        return this._super.apply(this, arguments);
    }
});

});
