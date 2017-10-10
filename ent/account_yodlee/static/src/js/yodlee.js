odoo.define('account_yodlee.acc_config_widget', function(require) {
"use strict";

var core = require('web.core');
var framework = require('web.framework');
var Widget = require('web.Widget');

var QWeb = core.qweb;


var YodleeAccountConfigurationWidget = Widget.extend({

    process_next_step: function() {
        var self = this;
        var provider_id, provider_name = false;
        if (this.login_form) {
            provider_id = this.login_form.provider[0].id;
            provider_name = this.login_form.provider[0].name;
        }
        var params = [];
        var inputs = $(".js_online_sync_input");
        var type = $(".js_online_sync_input").parents('div').data('type');
        if (type === 'questionAndAnswer') {
            params = this.refresh_info.providerAccount.loginForm;
        }

        _.each(inputs, function(input,i){
            var value = input.value;
            var field_id = $(input).attr('field-id');
            var row_id = $(input).attr('row-id');
            var required = $(input).attr('isOptional');
            if (type === 'questionAndAnswer') {
                _.filter(params.row, function(field) {
                    _.filter(field.field, function(f) {
                        if (f.id === field_id) {
                            f.value = value;
                        }
                    });
                });
            }
            else {
                params.push({value: value, field_id: field_id, row_id: row_id, required: required});
                
            }
        });
        if (this.in_rpc_call === false){
            this.blockUI(true);
            self.$('.js_wait_updating_account').toggleClass('hidden');
            this._rpc({
                    model: 'account.online.provider',
                    method: 'yodlee_add_update_provider_account',
                    args: [[this.id], params, provider_id, provider_name],
                })
                .then(function(result){
                    // ProviderAccount has succesfully been created/updated on yodlee and is being refreshed
                    // We need to keep calling the refresh API until it is done to know if we have some error or mfa
                    // (bad credentials, captcha, success)
                    framework.blockUI();
                    self.id = result;
                    return self._rpc({
                            model: 'account.online.provider',
                            method: 'refresh_status',
                            args: [[self.id]],
                        })
                        .then(function(result) {
                            self.blockUI(false);
                            self.refresh_info = result;
                            self.renderElement();
                        });
                }).fail(function(result){
                    // If we have an error and we are in a captcha process, hide continue button and force user to
                    // ask for a new captcha.
                    if (self.$('.js_new_captcha').length > 0) {
                        self.$('.js_process_next_step').addClass('hidden');
                    }
                    self.$('.js_wait_updating_account').toggleClass('hidden');
                    self.blockUI(false);
                });
        }
    },

    get_new_captcha: function() {
        var self = this;
        this.blockUI(true);
        return this._rpc({
                model: 'account.online.provider',
                method: 'manual_sync',
                args: [[self.id], false],
            })
            .then(function(result) {
                self.blockUI(false);
                self.refresh_info = result;
                self.renderElement();
            }).fail(function(result){
                self.$('.js_wait_updating_account').toggleClass('hidden');
                self.blockUI(false);
            });
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

    parse_image: function() {
        if (this.refresh_info.providerAccount.loginForm.formType === 'image') {
            // We have to show an image, but first we have to convert the binary array into a base64
            _.each(this.refresh_info.providerAccount.loginForm.row, function(row, index){
                _.each(row.field, function(field, index){
                    var image;
                    if (field.image) {
                        image = "";
                        var image_array = new Uint8Array(field.image);
                        _.each(image_array, function(v,k){
                            image = image + String.fromCharCode(v);
                        });
                        field.image = btoa(image);
                    }
                });
            });
        }
    },

    bind_button: function() {
        var self = this;
        this.$('.js_process_next_step').click(function(){
            self.process_next_step();
        });
        this.$('.js_new_captcha').click(function(){
            self.get_new_captcha();
        });
        this.$('.js_process_cancel').click(function(){
            self.$el.parents('.modal').modal('hide');
        });
    },

    init: function(parent, context) {
        this._super(parent, context);
        this.login_form = context.login_form;
        this.refresh_info = context.refresh_info;
        this.in_rpc_call = false;
        // In case we launch wizard in an advanced step (like updating credentials or mfa)
        // We need to set this.init_call to false and this.id (both should be in context)
        this.init_call = true;
        this.context = context.context;
        if (context.context.init_call !== undefined) {
            this.init_call = context.context.init_call;
        }
        if (context.context.provider_account_identifier !== undefined) {
            this.id = context.context.provider_account_identifier;
        }
        if (context.context.open_action_end !== undefined) {
            this.action_end = context.context.open_action_end;
        }
    },


    renderElement: function() {
        var self = this;
        var fields = {};
        if (this.refresh_info && this.refresh_info.providerAccount.refreshInfo.status === 'SUCCESS') {
            if (this.action_end) {
                return this._rpc({
                        model: 'account.online.provider',
                        method: 'open_action',
                        args: [[self.id], this.action_end, this.refresh_info.numberAccountAdded, this.context],
                    })
                    .then(function(result) {
                        self.do_action(result);
                    });
            }
            else {
                var local_dict = {
                                init_call: this.init_call, 
                                number_added: this.refresh_info.numberAccountAdded,
                                transactions: this.refresh_info.transactions,};
                self.replaceElement($(QWeb.render('Success', local_dict)));
            }
        }
        else {
            if (this.login_form) {
                fields = this.login_form.provider[0];
            }
            if (this.refresh_info !== undefined) {
                fields = this.refresh_info.providerAccount;
                self.parse_image();
            }
            this.replaceElement($(QWeb.render('YodleeLoginTemplate', {widget: fields})));
        }
        this.bind_button();
    },

});

core.action_registry.add('yodlee_online_sync_widget', YodleeAccountConfigurationWidget);
    
});
