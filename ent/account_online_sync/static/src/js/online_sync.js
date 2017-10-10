odoo.define('account_online_sync.acc_config_widget', function(require) {
"use strict";

var core = require('web.core');
var framework = require('web.framework');
var Widget = require('web.Widget');
var QWeb = core.qweb;

var OnlineSyncAccountInstitutionSelector = Widget.extend({
    template: 'OnlineSyncSearchBank',
    init: function(parent, context) {
        this._super(parent, context);
        this.search_allowed = true;
        if (context.context !== undefined) {
            this.show_select_button = context.context.show_select_button || false;
            this.context = context.context;
        }
    },

    renderElement: function() {
        var self = this;
        this._super();
        this.$('#search_form').submit(function(event){
            event.preventDefault();
            event.stopPropagation();
            self.search_institution();
        });
        this.$('#click_search_institution').click(function(){
            self.search_institution();
        });
    },

    search_institution: function() {
        var self = this;
        if (self.search_allowed === true) {
            //search_allowed is used to prevent doing multiple RPC call during the search time
            self.search_allowed = false;
            framework.blockUI();
            return this._rpc({
                    model: 'account.online.provider',
                    method: 'get_institution',
                    args: [[], self.$('#search_institution').val()],
                })
                .then(function(result){
                    framework.unblockUI();
                    self.institution_list = result;
                    var $inst_list = $(QWeb.render('OnlineSyncInstitutionsList', {institutions: result, length: result.length}));
                    self.$el.siblings('.institution_result').replaceWith($inst_list);
                    self.$el.siblings('.institution_result').find('#table_institution_result tbody tr').click(function() {
                        var id = $(this).data('id');
                        var inst = result.filter(function(o) {return o.id === id});
                        var $inst_detail = $(QWeb.render('OnlineSyncInstitutionsDetail', {institution: inst[0], show_select_button: self.show_select_button}));
                        self.$el.siblings('.institution_detail').replaceWith($inst_detail);
                        self.$el.siblings('.institution_result').hide();
                        self.$el.siblings('.institution_search').hide();
                        self.$el.siblings('.institution_detail').find('.js_return_list_institution').click(function(){
                            self.$el.siblings('.institution_result').show();
                            self.$el.siblings('.institution_search').show();
                            self.$el.siblings('.institution_detail').hide();
                        });
                        self.$el.siblings('.institution_detail').find('.js_choose_institution').click(function(){
                            // Open new client action
                            $(this).parent().find('.btn').toggleClass('disabled');
                            return this._rpc({
                                    model: 'account.online.provider',
                                    method: 'get_login_form',
                                    args: [[], inst[0].id, inst[0].type_provider, self.context],
                                })
                                .then(function(result){
                                    self.do_action(result);
                                });
                        });
                    });
                    self.search_allowed = true;
                }).fail(function(){
                    framework.unblockUI();
                    // If RPC call failed (might be due to error because search string is less than 3 char), unblock search
                    self.search_allowed = true;
                });
        }
    },

});
core.action_registry.add('online_sync_institution_selector', OnlineSyncAccountInstitutionSelector);
});