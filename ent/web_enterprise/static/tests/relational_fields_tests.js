odoo.define('web_enterprise.relational_fields_tests', function (require) {
"use strict";

var FormView = require('web.FormView');
var testUtils = require('web.test_utils');

var createView = testUtils.createView;

QUnit.module('web_enterprise', {}, function () {

QUnit.module('relational_fields', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    display_name: { string: "Displayed name", type: "char" },
                    trululu: {string: "Trululu", type: "many2one", relation: 'partner'},
                },
                records: [{
                    id: 1,
                    display_name: "first record",
                    trululu: 4,
                }, {
                    id: 2,
                    display_name: "second record",
                    trululu: 1,
                }, {
                    id: 4,
                    display_name: "aaa",
                }],
            },
        };
    }
}, function () {

    QUnit.module('FieldStatus');

    QUnit.test('statusbar is rendered correclty on small devices', function (assert) {
        assert.expect(6);

        var form = createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch:
                '<form string="Partners">' +
                    '<header><field name="trululu" widget="statusbar"/></header>' +
                    '<field name="display_name"/>' +
                '</form>',
            res_id: 1,
            config: {device: {isMobile: true}},
        });

        assert.strictEqual(form.$('.o_statusbar_status > button:contains(aaa)').length, 1,
            "should have only one visible status in mobile, the active one");
        assert.strictEqual(form.$('.o_statusbar_status .o-status-more').length, 1,
            "should have a dropdown containing all status");
        assert.strictEqual(form.$('.o_statusbar_status .o-status-more:visible').length, 0,
            "dropdown should be hidden");

        // open the dropdown
        form.$('.o_statusbar_status > button').click();
        assert.strictEqual(form.$('.o_statusbar_status .o-status-more:visible').length, 1,
            "dropdown should be visible");
        assert.strictEqual(form.$('.o_statusbar_status .o-status-more li').length, 3,
            "should have 3 status");
        var $activeStatus = form.$('.o_statusbar_status .o-status-more li button[data-value=4]');
        assert.ok($activeStatus.hasClass('btn-primary'), "active status should be btn-primary");

        form.destroy();
    });

    QUnit.test('statusbar with no status on extra small screens', function (assert) {
        assert.expect(9);

        var form = createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch:'<form string="Partners">' +
                    '<header><field name="trululu" widget="statusbar"/></header>' +
                '</form>',
            res_id: 4,
            config: {device: {isMobile: true}},
        });

        assert.ok(form.$('.o_statusbar_status').hasClass('o_field_empty'),
            'statusbar widget should have class o_field_empty');
        assert.strictEqual(form.$('.o_statusbar_status').children().length, 2,
            'statusbar widget should have two children');
        assert.strictEqual(form.$('.o_statusbar_status button.dropdown-toggle').length, 1,
            'statusbar widget should have a button');
        assert.strictEqual(form.$('.o_statusbar_status button.dropdown-toggle').text().trim(), '',
            'statusbar button has no text');  // Behavior as of saas-15, might be improved
        assert.strictEqual(form.$('.o_statusbar_status ul').length, 1,
            'statusbar widget should have a ul');
        assert.strictEqual(form.$('.o_statusbar_status ul li').length, 3,
            'statusbar widget dropdown menu should have 3 li');
        assert.strictEqual(form.$('.o_statusbar_status ul li').eq(0).text().trim(), 'first record',
            'statusbar widget dropdown first li should display the first record display_name');
        assert.strictEqual(form.$('.o_statusbar_status ul li').eq(1).text().trim(), 'second record',
            'statusbar widget dropdown second li should display the second record display_name');
        assert.strictEqual(form.$('.o_statusbar_status ul li').eq(2).text().trim(), 'aaa',
            'statusbar widget dropdown three li should display the third record display_name');
        form.destroy();
    });
});
});
});
