odoo.define('web_mobile.session', function (require) {
"use strict";

var session = require('web.Session');

var mobile = require('web_mobile.rpc');

/*
    Android webview not supporting post download and odoo is using post method to download
    so here override get_file of session and passed all data to native mobile downloader
    ISSUE: https://code.google.com/p/android/issues/detail?id=1780
*/

session.include({

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    get_file: function (options) {
        if (mobile.methods.downloadFile) {
            mobile.methods.downloadFile(options);
            if (options.complete) { options.complete(); }
        } else {
            this._super.apply(this, arguments);
        }
    },
});

});
