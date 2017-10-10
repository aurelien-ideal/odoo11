odoo.define('account_batch_deposit.reconciliation_tests.data', function (require) {
"use strict";

var data = require('account.reconciliation_tests.data');

data.params.data["account.bank.statement"].get_batch_deposits_data = function (args) {
    return $.when();
};

data.params.data["account.bank.statement.line"].get_move_lines_for_reconciliation_widget_by_batch_deposit_id = function (args) {
    return $.when(data.params.mv_lines['[5,"b",0,6]']);
};

data.params.data_preprocess.batch_deposits = [{
    'amount_currency_str': false,
    'journal_id': 84,
    'id': 1,
    'amount_str': "$ 10,980.00",
    'name': "DEPOSIT/2017/0001"
}];

});

odoo.define('account_batch_deposit.reconciliation_tests', function (require) {
"use strict";

var ReconciliationClientAction = require('account.ReconciliationClientAction');
var demoData = require('account.reconciliation_tests.data');
var testUtils = require('web.test_utils');

QUnit.module('account', {
    beforeEach: function () {
        this.params = demoData.getParams();
    }
}, function () {
    QUnit.module('Reconciliation');

    QUnit.test('Reconciliation basic rendering with account_batch_deposit', function (assert) {
        assert.expect(4);

        var clientAction = new ReconciliationClientAction.StatementAction(null, this.params.options);
        testUtils.addMockEnvironment(clientAction, {
            data: this.params.data,
        });
        clientAction.appendTo($('#qunit-fixture'));

        assert.strictEqual(clientAction.widgets[0].$('.batch_deposits_selector').length, 0,
            "should not have 'Select a Batch Deposit' button");

        var widget = clientAction.widgets[1];
        widget.$('.accounting_view thead td:first').trigger('click');
        assert.strictEqual(widget.$('.batch_deposits_selector').length, 1,
            "should display 'Select a Batch Deposit' button");

        assert.strictEqual(widget.$('.accounting_view tbody tr').length, 0,
            "should have not reconciliation propositions");

        widget.$('.match .batch_deposits_selector:first').trigger('click');
        widget.$('.match a.batch_deposit:first').trigger('click');

        assert.strictEqual(widget.$('.accounting_view tbody tr').length, 2,
            "should have 2 reconciliation propositions");

        clientAction.destroy();
    });

});
});
