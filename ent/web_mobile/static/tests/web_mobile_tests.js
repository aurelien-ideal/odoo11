odoo.define('web_mobile.tests', function (require) {
"use strict";

var FormView = require('web.FormView');
var testUtils = require('web.test_utils');

var mobile = require('web_mobile.rpc');

var createView = testUtils.createView;

QUnit.module('web_mobile', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    name: {},
                    image: {},
                    parent_id: {string: "Parent", type: "many2one", relation: 'partner'},
                    phone: {},
                    mobile: {},
                    email: {},
                    street: {},
                    street2: {},
                    city: {},
                    state_id: {},
                    zip: {},
                    country_id: {},
                    website: {},
                    function: {},
                    title: {},
                },
                records: [{
                    id: 1,
                    name: 'coucou',
                }, {
                    id: 2,
                    name: 'coucou',
                }, {
                    id: 11,
                    name: 'coucou',
                    image: 'image',
                    parent_id: 1,
                    phone: 'phone',
                    mobile: 'mobile',
                    email: 'email',
                    street: 'street',
                    street2: 'street2',
                    city: 'city',
                    state_id: 'state_id',
                    zip: 'zip',
                    country_id: 'country_id',
                    website: 'website',
                    function: 'function',
                    title: 'title',
                }],
            },
        };
    },
}, function () {

    QUnit.test("contact sync in a non-mobile environment", function (assert) {
        assert.expect(2);

        var rpcCount = 0;

        var form = createView({
            View: FormView,
            arch: '<form>' +
                    '<sheet>' +
                        '<div name="button_box">' +
                            '<contactsync> </contactsync>' +
                        '</div>' +
                        '<field name="name"/>' +
                    '</sheet>' +
                  '</form>',
            data: this.data,
            model: 'partner',
            mockRPC: function () {
                rpcCount++;
                return this._super.apply(this, arguments);
            },
            res_id: 11,
        });

        var $button = form.$('div.oe_stat_button[widget="contact_sync"]');

        assert.strictEqual($button.length, 0, "the tag should not be visible in a non-mobile environment");
        assert.strictEqual(rpcCount, 1, "no extra rpc should be done by the widget (only the one from the view)");

        form.destroy();
    });

    QUnit.test("contact sync in a mobile environment", function (assert) {
        assert.expect(5);


        var __addContact = mobile.methods.addContact;
        var addContactRecord;
        // override addContact to simulate a mobile environment
        mobile.methods.addContact = function (r) {
            addContactRecord = r;
        };

        var rpcDone;
        var rpcCount = 0;

        var form = createView({
            View: FormView,
            arch:
                '<form>' +
                    '<sheet>' +
                        '<div name="button_box">' +
                            '<contactsync> </contactsync>' +
                        '</div>' +
                        '<field name="name"/>' +
                    '</sheet>' +
                '</form>',
            data: this.data,
            model: 'partner',
            mockRPC: function (route, args) {
                if (args.method === "read" && args.args[0] === 11 && _.contains(args.args[1], 'phone')) {
                    rpcDone = true;
                }
                rpcCount++;
                return this._super(route, args);
            },
            res_id: 11,
        });

        var $button = form.$('div.oe_stat_button[widget="contact_sync"]');

        assert.strictEqual($button.length, 1, "the tag should be visible in a mobile environment");
        assert.strictEqual(rpcCount, 1, "no extra rpc should be done by the widget (only the one from the view)");

        $button.click();

        assert.strictEqual(rpcCount, 2, "an extra rpc should be done on click");
        assert.ok(rpcDone, "a read rpc should have been done");
        assert.deepEqual(addContactRecord, [{
            "city": "city",
            "country_id": "country_id",
            "email": "email",
            "function": "function",
            "id": 11,
            "image": "image",
            "mobile": "mobile",
            "name": "coucou",
            "parent_id":  [
                1,
                "coucou",
            ],
            "phone": "phone",
            "state_id": "state_id",
            "street": "street",
            "street2": "street2",
            "title": "title",
            "website": "website",
            "zip": "zip"
        }], "all data should be correctly passed");

        mobile.methods.addContact = __addContact;

        form.destroy();
    });

    QUnit.test("many2one in a mobile environment", function (assert) {
        assert.expect(3);

        var mobileDialogCall = 0;

        // override addContact to simulate a mobile environment
        var __addContact = mobile.methods.addContact;
        var __many2oneDialog = mobile.methods.many2oneDialog;

        mobile.methods.addContact = true;
        mobile.methods.many2oneDialog = function () {
            mobileDialogCall++;
            return $.when({data: {}});
        };

        var form = createView({
            View: FormView,
            arch:
                '<form>' +
                    '<sheet>' +
                        '<field name="parent_id"/>' +
                    '</sheet>' +
                '</form>',
            data: this.data,
            model: 'partner',
            res_id: 2,
            viewOptions: {mode: 'edit'},
        });

        var $input = form.$('input');

        assert.ok($input.prop('disabled'), "the many2one should be disabled in a mobile environment");
        assert.strictEqual(mobileDialogCall, 0, "the many2one should be disabled in a mobile environment");

        $input.click();

        assert.strictEqual(mobileDialogCall, 1, "the many2one should call a special dialog in a mobile environment");

        mobile.methods.addContact = __addContact;
        mobile.methods.many2oneDialog = __many2oneDialog;

        form.destroy();
    });
});
});
