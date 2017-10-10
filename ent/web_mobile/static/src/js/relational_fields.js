odoo.define('web_mobile.relational_fields', function (require) {
"use strict";

var relational_fields = require('web.relational_fields');

var mobile = require('web_mobile.rpc');

/**
 * Override the Many2One to open a dialog in mobile.
 */

relational_fields.FieldMany2One.include({

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _invokeMobileDialog: function (term) {
        var self = this;
        this._search(term).done(function (result) {
            self._callback_actions = {};

            _.each(result, function (r, i) {
                if (!r.hasOwnProperty('id')) {
                    self._callback_actions[i] = r.action;
                    result[i].action_id = i;
                }
            });
            mobile.methods.many2oneDialog({'records': result, 'label': self.string})
                .then(function (response) {
                    if (response.data.action === 'search') {
                        self._invokeMobileDialog(response.data.term);
                    }
                    if (response.data.action === 'select') {
                        self._setValue(response.data.value.id);
                    }
                    if (response.data.action === 'action') {
                        self._callback_actions[response.data.value.action_id]();
                    }
                });
        });
    },
    /**
     * @override
     * @private
     */
    _renderEdit: function () {
        this._super.apply(this, arguments);
        if (mobile.methods.many2oneDialog) {
            this.$('input').prop('disabled', true);
            this.$el.on('click', this._onMobileClick.bind(this));
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * We always open ManyToOne native dialog for select/update field value
     *
     * @private
     */
    _onMobileClick: function () {
        this._invokeMobileDialog('');
    },
});

});
