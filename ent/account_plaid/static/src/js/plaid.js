odoo.define('account_plaid.acc_config_widget', function(require) {
"use strict";

var core = require('web.core');
var framework = require('web.framework');
var QWeb = core.qweb;
var Widget = require('web.Widget');


var PlaidAccountConfigurationWidget = Widget.extend({

    call: function(params, mfa) {
        var self = this;
        if (this.in_rpc_call === false){
            this.blockUI(true);
            self.$('.js_wait_updating_account').toggleClass('hidden');
            var request = this._rpc({
                    model: 'account.online.provider',
                    method: 'plaid_add_update_provider_account',
                    args: [[this.id], params, this.site_info.id, this.site_info.name, mfa, this.context],
                })
                .then(function(result){
                    self.blockUI(false);
                    if (result.account_online_provider_id !== undefined) {
                        self.id = result.account_online_provider_id;
                    }
                    self.resp_json = result;
                    self.renderElement();
                })
                .fail(function(result){
                    self.$('.js_wait_updating_account').toggleClass('hidden');
                    self.blockUI(false);
                });
            return request;
        }
    },

    process_next_step: function() {
        var login = this.$('.js_plaid_login').val();
        var password = this.$('.js_plaid_password').val();
        var pin = this.$('.js_plaid_pin').val();
        var params = {username: login, password: password, type: this.site_info.type, options: '{"login_only": true, "list": true}'};
        if (pin !== '') {
            params.pin = pin;
        }
        return this.call(params, false);
    },

    blockUI: function(state) {
        this.in_rpc_call = state;
        this.$('.btn').toggleClass('disabled');
        if (state === true) {
            framework.blockUI();
        }
        else {
            framework.unblockUI();
        }
    },

    init: function(parent, context) {
        this._super(parent, context);
        this.site_info = context.site_info;
        this.resp_json = context.resp_json;
        this.in_rpc_call = false;
        // In case we launch wizard in an advanced step (like updating credentials or mfa)
        // We need to set this.init_call to false and this.id (both should be in context)
        this.init_call = true;
        if (context.context.init_call !== undefined) {
            this.init_call = context.context.init_call;
        }
        if (context.context.provider_account_identifier !== undefined) {
            this.id = context.context.provider_account_identifier;
        }
        if (context.context.open_action_end !== undefined) {
            this.action_end = context.context.open_action_end;
        }
        this.context = context.context;
    },

    bind_button: function() {
        var self = this;
        this.$('.js_process_next_step').click(function(){
            self.process_next_step();
        });
        this.$('.js_process_mfa_step').click(function(){
            self.process_mfa_step();
        });
        this.$('.js_process_cancel').click(function(){
            self.$el.parents('.modal').modal('hide');
        });
    },

    renderElement: function() {
        var self = this;
        if (this.resp_json && this.resp_json.action === 'success') {
            if (this.action_end) {
                return this._rpc({
                        model: 'account.online.provider',
                        method: 'open_action',
                        args: [[self.id], this.action_end, this.resp_json.numberAccountAdded, this.context],
                    })
                    .then(function(result) {
                        self.do_action(result);
                    });
            }
            else {
                var local_dict = {
                                init_call: this.init_call, 
                                number_added: this.resp_json.numberAccountAdded,
                                transactions: this.resp_json.transactions,};
                self.replaceElement($(QWeb.render('Success', local_dict)));
            }
        }
        else {
            var local_dict = {call: 'init'};
            if (this.resp_json && this.resp_json.action === 'mfa') {
                // this.show_mfa_to_user(this.resp_json);
                local_dict.call = 'mfa';
                local_dict.mfa = this.resp_json;
            }
            self.replaceElement($(QWeb.render('PlaidLogin', local_dict)));
        }
        self.bind_button();
    },

    process_mfa_step: function() {
        var params = {'access_token': this.resp_json.access_token, 'options': '{"login_only": true, "list": true}'}
        if ($('input[name="mfa-selection"]').length > 0){
            params['options'] = '{"send_method": {"mask": "'+ $('input[name="mfa-selection"]:checked').attr('mask') +'"}}';
        }
        else {
            //Get all input with information
            var $answers = $('.js_plaid_answer');
            var user_reply = [];
            if ($answers.length === 1){
                params['mfa'] = $answers.val();
            }
            else {
                $.each($answers, function(k,v){
                    user_reply = user_reply.concat(v.val());
                });
                params['mfa'] = JSON.stringify(user_reply);
            }
        }
        return this.call(params, true);
    },
});

core.action_registry.add('plaid_online_sync_widget', PlaidAccountConfigurationWidget);

});