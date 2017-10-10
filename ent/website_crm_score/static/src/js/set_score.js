odoo.define('website_crm_score.set_score', function (require) {
"use strict";

var ajax = require('web.ajax');
var rpc = require('web.rpc');
var websiteSeo = require('website.seo');
var weContext = require("web_editor.context");
var core = require('web.core');

var qweb = core.qweb;

ajax.loadXML('/website_crm_score/static/src/xml/track_page.xml', qweb);

websiteSeo.SeoConfigurator.include({
    track: null,
    start: function () {
        var def = this._super.apply(this, arguments);
        var self = this;
        var obj = websiteSeo.SeoConfigurator.prototype.getMainObject();
        // only display checkbox for website page
        if (obj && ['website.page', 'ir.ui.view'].indexOf(obj.model) != -1) {
            this.is_tracked().then(function (data) {
                var add = $('<input type="checkbox" required="required"/>');
                if (data[0]['track']) {
                    add.attr('checked','checked');
                    self.track = true;
                }
                else {
                    self.track = false;
                }
                self.$('h3[class="track-page"]').append(add);
            });
        }
        return def;
    },
    is_tracked: function (val) {
        var obj = websiteSeo.SeoConfigurator.prototype.getMainObject();
        if (!obj) {
            return $.Deferred().reject();
        } else {
            return rpc.query({
                    model: obj.model,
                    method: 'read',
                    args: [[obj.id], ['track'], weContext.get()],
                });
        }
    },
    update: function () {
        var self = this;
        var mysuper = this._super;
        var checkbox_value = this.$('input[type="checkbox"]').is(':checked');
        if (checkbox_value !== self.track) {
            this.trackPage(checkbox_value).then(function () {
                mysuper.call(self);
            });
        }
        else {
            mysuper.call(self);
        }
    },
    trackPage: function (val) {
        var obj = websiteSeo.SeoConfigurator.prototype.getMainObject();
        if (!obj) {
            return $.Deferred().reject();
        } else {
            return rpc.query({
                    model: obj.model,
                    method: 'write',
                    args: [[obj.id], { track: val }, weContext.get()],
                });
        }
    },
});

});
