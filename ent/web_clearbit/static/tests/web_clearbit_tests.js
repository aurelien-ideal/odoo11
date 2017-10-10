odoo.define('web_clearbit.tests', function (require) {
"use strict";

var FormView = require('web.FormView');
var testUtils = require("web.test_utils");
var FieldClearbit = require('web_clearbit.field');

var createView = testUtils.createView;

QUnit.module('web_clearbit', {
    before: function () {
        this.__field_clearbit_debounce = FieldClearbit.prototype.debounceSuggestions;
        FieldClearbit.prototype.debounceSuggestions = 0;

        // TODO mock these instead of overriding them

        this.__field_clearbit_getBase64Image = FieldClearbit.prototype._getBase64Image;
        FieldClearbit.prototype._getBase64Image = function (url) {
            return $.when(url === "odoo.com/logo.png" ? "odoobase64" : "");
        };

        this.__field_clearbit_getClearbitValues = FieldClearbit.prototype._getClearbitValues;
        var suggestions = [
            {name: "Odoo", domain: "odoo.com", logo: "odoo.com/logo.png"}
        ];
        FieldClearbit.prototype._getClearbitValues = function (value) {
            this.suggestions = _.filter(suggestions, function (suggestion) {
                return (suggestion.name.toLowerCase().indexOf(value.toLowerCase()) >= 0);
            });
            return $.when();
        };
    },
    beforeEach: function () {
        this.data = {
            'res.partner': {
                fields: {
                    company_type: {string: "Company Type", type: "selection", selection: [["company", "Company"], ["individual", "Individual"]], searchable: true},
                    name: {string: "Name", type: "char", searchable: true},
                    website: {string: "Website", type: "char", searchable: true},
                    image: {string: "Image", type: "binary", searchable: true},
                },
                records: [],
                onchanges: {},
            },
        };
    },
    after: function () {
        FieldClearbit.prototype.debounceSuggestions = this.__field_clearbit_debounce;
        delete this.__field_clearbit_debounce;

        FieldClearbit.prototype._getBase64Image = this.__field_clearbit_getBase64Image;
        delete this.__field_clearbit_getBase64Image;

        FieldClearbit.prototype._getClearbitValues = this.__field_clearbit_getClearbitValues;
        delete this.__field_clearbit_getClearbitValues;
    },
}, function () {
    QUnit.test("clearbit field: basic usage", function (assert) {
        assert.expect(13);

        var form = createView({
            View: FormView,
            model: 'res.partner',
            data: this.data,
            arch:
                '<form>' +
                    '<field name="company_type"/>' +
                    '<field name="name" widget="field_clearbit"/>' +
                    '<field name="website"/>' +
                    '<field name="image" widget="image"/>' +
                '</form>',
            mockRPC: function (route, args) {
                if (args.method) {
                    assert.step(args.method);
                }
                if (route === "/web/static/src/img/placeholder.png"
                    || route === "odoo.com/logo.png"
                    || route === "data:image/png;base64,odoobase64") { // land here as it is not valid base64 content
                    return $.when();
                }
                return this._super.apply(this, arguments);
            },
        });

        // Checks for individual
        var $company_type = form.$("select[name='company_type']");
        $company_type.val('"individual"').trigger('change');

        var $input = form.$(".o_field_clearbit > input:visible");
        assert.strictEqual($input.length, 1,
            "there should be an <input/> for the clearbit field");
        $input.val("od").trigger("input");
        var $dropdown = form.$(".o_field_clearbit .dropdown-menu:visible");
        assert.strictEqual($dropdown.length, 0,
            "there should not be an opened dropdown");

        // Checks for company
        $company_type.val('"company"').trigger('change');

        var $input = form.$(".o_field_clearbit > input:visible");
        assert.strictEqual($input.length, 1,
            "there should be an <input/> for the clearbit field");

        $input.val("od").trigger("input");
        var $dropdown = form.$(".o_field_clearbit .dropdown-menu:visible");
        assert.strictEqual($dropdown.length, 1,
            "there should be an opened dropdown");
        assert.strictEqual($dropdown.children().length, 1,
            "there should be one proposition (Odoo)");

        $dropdown.find("a").first().click();
        $input = form.$(".o_field_clearbit > input");
        assert.strictEqual($input.val(), "Odoo",
            "name value should have been updated to \"Odoo\"");
        assert.strictEqual(form.$("input.o_field_widget").val(), "odoo.com",
            "website value should have been updated to \"odoo.com\"");
        assert.strictEqual(form.$(".o_field_image img").attr("src"), "#test:data:image/png;base64,odoobase64",
            "image value should have been updated to \"odoobase64\"");

        $input.val("test").trigger("input");
        $dropdown = form.$(".o_field_clearbit .dropdown-menu:visible");
        assert.strictEqual($dropdown.length, 0,
            "there should not be an opened dropdown when there is no suggestion");

        $input.val("oo").trigger("input");
        $dropdown = form.$(".o_field_clearbit .dropdown-menu:visible");
        assert.strictEqual($dropdown.length, 1,
            "there should be an opened dropdown when typing odoo letters again");

        $input.trigger("focusout");
        $dropdown = form.$(".o_field_clearbit .dropdown-menu:visible");
        assert.strictEqual($dropdown.length, 0,
            "unfocusing the input should close the dropdown");

        assert.verifySteps(["default_get"]);
        form.destroy();
    });
});
});
