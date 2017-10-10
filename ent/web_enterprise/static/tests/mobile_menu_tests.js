odoo.define('web_enterprise.mobile_menu_tests', function (require) {
"use strict";

// Temporarily disable these tests, until we add a specific test suite for mobile
return;

var ActionManager = require('web.ActionManager');
var Menu = require('web_enterprise.Menu');
var testUtils = require('web.test_utils');

QUnit.module('web_enterprise mobile_menu_tests', {
    beforeEach: function () {
        this.data = {
            all_menu_ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            name: "root",
            children: [{
                id: 1,
                name: "Discuss",
                children: [],
             }, {
                 id: 2,
                 name: "Calendar",
                 children: []
             }, {
                id: 3,
                name: "Contacts",
                children: [{
                    id: 4,
                    name: "Contacts",
                    children: [],
                }, {
                    id: 5,
                    name: "Configuration",
                    children: [{
                        id: 6,
                        name: "Contact Tags",
                        children: [],
                    }, {
                        id: 7,
                        name: "Contact Titles",
                        children: [],
                    }, {
                        id: 8,
                        name: "Localization",
                        children: [{
                            id: 9,
                            name: "Countries",
                            children: [],
                        }, {
                            id: 10,
                            name: "Fed. States",
                            children: [],
                        }],
                    }],
                 }],
           }],
        };
    }
}, function () {

    QUnit.module('Burger Menu');

    QUnit.test('Burger Menu on appswitcher', function (assert) {
        assert.expect(1);

        function createParent (params) {
            var actionManager = new ActionManager();
            testUtils.addMockEnvironment(actionManager, params);
            return actionManager;
        }

        var parent = createParent({
            data: {},
            config: {device: {isMobile: true}},
        });

        var mobileMenu = new Menu(parent, this.data);
        testUtils.addMockEnvironment(mobileMenu, {
            mockRPC: function () {
                return $.when([]);
            },
        });
        mobileMenu.appendTo($('#qunit-fixture'));

        mobileMenu.$('.o_mobile_menu_toggle').click();
        assert.ok(!$(".o_burger_menu").hasClass('o_hidden'),
            "Burger menu should be opened on button click");
        mobileMenu.$('.o_burger_menu_close').click();

        parent.destroy();
    });

    QUnit.test('Burger Menu on an App', function (assert) {
        assert.expect(3);
        function createParent (params) {
            var actionManager = new ActionManager();
            testUtils.addMockEnvironment(actionManager, params);
            return actionManager;
        }

        var parent = createParent({
            data: {},
            config: {device: {isMobile: true}},
        });

        var mobileMenu = new Menu(parent, this.data);
        testUtils.addMockEnvironment(mobileMenu, {
            mockRPC: function () {
                return $.when([]);
            },
        });
        mobileMenu.appendTo($('#qunit-fixture'));
        mobileMenu.change_menu_section(3);
        mobileMenu.toggle_mode(false);

        mobileMenu.$('.o_mobile_menu_toggle').click();
        assert.ok(!$(".o_burger_menu").hasClass('o_hidden'),
            "Burger menu should be opened on button click");
        $('.o_burger_menu_topbar').click();
        assert.ok(!$(".o_burger_menu_content").hasClass('o_burger_menu_dark'),
            "Toggle to usermenu on header click");
        $('.o_burger_menu_topbar').click();
        assert.ok($(".o_burger_menu_content").hasClass('o_burger_menu_dark'),
            "Toggle back to main sales menu on header click");

        parent.destroy();
    });
});
});
