odoo.define('account_batch_deposit.reconciliation', function (require) {
"use strict";

var ReconciliationClientAction = require('account.ReconciliationClientAction');
var ReconciliationModel = require('account.ReconciliationModel');
var ReconciliationRenderer = require('account.ReconciliationRenderer');
var core = require('web.core');

var _t = core._t;
var QWeb = core.qweb;

//--------------------------------------------------------------------------

var Action = {
    custom_events: _.defaults({
        select_deposit: '_onAction',
    }, ReconciliationClientAction.StatementAction.prototype.custom_events),
};

ReconciliationClientAction.StatementAction.include(Action);
ReconciliationClientAction.ManualAction.include(Action);

//--------------------------------------------------------------------------

var Model = {
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.batchDeposits = [];
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     *
     * @param {Object} context
     * @param {number[]} context.statement_ids
     * @returns {Deferred}
     */
    load: function (context) {
        var self = this;
        return this._super(context).then(function () {
            self.batchDeposits = self.statement && self.statement.batch_deposits || [];
        });
    },
    /**
     *
     * @param {string} handle
     * @param {number} depositId
     * @returns {Deferred}
     */
    selectDeposit: function(handle, depositId) {
        return this._rpc({
                model: 'account.bank.statement.line',
                method: 'get_move_lines_for_reconciliation_widget_by_batch_deposit_id',
                args: [this.getLine(handle).id, depositId],
            })
            .then(this._addSelectedDepositLines.bind(this, handle, depositId));
    },

    /**
     * @override
     *
     * @param {(string|string[])} handle
     * @returns {Deferred<Object>} resolved with an object who contains
     *   'handles' key
     */
    validate: function (handle) {
        var self = this;
        return this._super(handle).then(function (data) {
            if (_.any(data.handles, function (handle) {
                    return !!self.getLine(handle).batch_deposit_id;
                })) {
                return self._updateBatchDeposits().then(function () {
                    return data;
                });
            }
            return data;
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     *
     * @private
     * @param {Object}
     * @returns {Deferred}
     */
    _computeLine: function (line) {
        if (line.st_line.partner_id) {
            line.relevant_deposits = [];
        } else {
            // Select deposits from the same journal as the bank statement
            line.relevant_deposits = _.filter(this.batchDeposits, function (batch_deposit) {
                return batch_deposit.journal_id === line.st_line.journal_id;
            });
        }
        return this._super.apply(this, arguments);
    },
    /**
     *
     * @private
     * @param {string} handle
     * @param {number} depositId
     * @returns {Deferred}
     */
    _addSelectedDepositLines: function (handle, depositId, depositLines) {
        var line = this.getLine(handle);
        // Check if some lines are already selected in another reconciliation
        var selectedIds = [];
        for (var hand in this.lines) {
            if (handle === hand) {
                continue;
            }
            var rec = this.lines[hand].reconciliation_proposition || [];
            for (var k in rec) {
                if (!isNaN(rec[k].id)) {
                    selectedIds.push(rec[k].id);
                }
            }
        }
        selectedIds = _.filter(depositLines, function (deposit_line) {
            return selectedIds.indexOf(deposit_line.id) !== -1;
        });
        if (selectedIds.length > 0) {
            var message = _t("Some journal items from the selected batch deposit are already selected in another reconciliation : ");
            message += _.map(selectedIds, function(l) { return l.name; }).join(', ');
            this.do_warn(_t("Incorrect Operation"), message, true);
            return;
        }

        // remove double
        if (line.reconciliation_proposition) {
            depositLines = _.filter(depositLines, function (deposit_line) {
                return !_.any(line.reconciliation_proposition, function (prop) {
                    return prop.id === deposit_line.id;
                });
            });
        }

        // add deposit lines as proposition
        this._formatLineProposition(line, depositLines);
        for (var k in depositLines) {
            this._addProposition(line, depositLines[k]);
        }
        line.batch_deposit_id = depositId;
        return $.when(this._computeLine(line), this._performMoveLine(handle));
    },
    /**
     * load data from
     * - 'account.bank.statement' fetch the batch deposits data
     *
     * @param {number[]} statement_ids
     * @returns {Deferred}
     */
    _updateBatchDeposits: function(statement_ids) {
        var self = this;
        return this._rpc({
                model: 'account.bank.statement',
                method: 'get_batch_deposits_data',
                args: [statement_ids],
            })
            .then(function (data) {
                self.batchDeposits = data;
            });
    },
};

ReconciliationModel.StatementModel.include(Model);
ReconciliationModel.ManualModel.include(Model);

//--------------------------------------------------------------------------

var Renderer = {
    events: _.defaults({
        "click .batch_deposit": "_onDeposit",
    }, ReconciliationRenderer.LineRenderer.prototype.events),

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     *
     * @param {object} state - statement line
     */
    update: function (state) {
        this._super(state);
        this.$(".match_controls .batch_deposits_selector").remove();
        if (state.relevant_deposits.length) {
            this.$(".match_controls .filter").after(QWeb.render("batch_deposits_selector", {
                batchDeposits: state.relevant_deposits,
            }));
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     *
     * @param {MouseEvent} event
     */
    _onDeposit: function(e) {
        e.preventDefault();
        var depositId = parseInt(e.currentTarget.dataset.batch_deposit_id);
        this.trigger_up('select_deposit', {'data': depositId});
    },
};

ReconciliationRenderer.LineRenderer.include(Renderer);
ReconciliationRenderer.ManualLineRenderer.include(Renderer);

});
