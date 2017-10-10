odoo.define('web_studio.bus', function (require) {
"use strict";

var Bus = require('web.Bus');

var bus = new Bus();

/* Events on this bus
 * ==================
 *
 * `studio_toggled`
 *      Studio has been toggled
 *      @param mode: ['app_creator', 'main']
 *      @param action: the current action (which will be customized with Studio)
 *      @param active_view: the action active view
 *
 * `action_changed`
 *      the action used by Studio has been changed (updated server side).
 *      @param action: the updated action
 *
 * `edition_mode_entered`
 *      the view has entered in edition mode.
 *      @param view_type
 *
 * `(un,re)do_clicked`
 *      during the view edition, the button (un,re)do has been clicked.
 *
 * `(un,re)do_available`
 *      during the view edition, the button (un,re)do has become available.
 *
 * `(un,re)do_not_available`
 *      during the view edition, the button (un,re)do has become unavailable.
 *
 */

bus.on('studio_toggled', null, function (mode) {
    var qs = $.deparam.querystring();
    if (mode) {
        qs.studio = mode;
    } else {
        delete qs.studio;
    }
    var l = window.location;
    var url = l.protocol + "//" + l.host + l.pathname + '?' + $.param(qs) + l.hash;
    window.history.pushState({ path:url }, '', url);
});

return bus;

});
