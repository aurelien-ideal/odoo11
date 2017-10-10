odoo.define('web_clearbit.field', function (require) {
'use strict';

var basic_fields = require('web.basic_fields');
var concurrency = require('web.concurrency');
var core = require('web.core');
var field_registry = require('web.field_registry');

var QWeb = core.qweb;

var FieldChar = basic_fields.FieldChar;

/**
 * FieldChar extension to suggest existing companies when changing the company
 * name on a res.partner view (indeed, it is designed to change the "name",
 * "website" and "image" fields of records of this model).
 */
var FieldClearbit = FieldChar.extend({
    className: 'o_field_clearbit',
    debounceSuggestions: 400,
    resetOnAnyFieldChange: true,

    events: _.extend({}, FieldChar.prototype.events, {
        'keyup': '_onKeyup',
        'mousedown .o_clearbit_suggestion': '_onMousedown',
        'focusout': '_onFocusout',
        'mouseenter .o_clearbit_suggestion': '_onHoverDropdown',
        'click .o_clearbit_suggestion': '_onSuggestionClicked',
    }),

    /**
     * @constructor
     * Prepares the basic rendering of edit mode by setting the root to be a
     * div.dropdown.open.
     * @see FieldChar.init
     */
    init: function () {
        this._super.apply(this, arguments);
        if (this.model !== 'res.partner') {
            return;
        }
        if (this.mode === 'edit') {
            this.tagName = 'div';
            this.className += ' dropdown open';
        }
        if (this.debounceSuggestions > 0) {
            this._suggestCompanies = _.debounce(this._suggestCompanies.bind(this), this.debounceSuggestions);
        }
        this._clearbitDropPrevious = new concurrency.DropPrevious();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Returns a deferred which will be resolved with the base64 data of the
     * image fetched from the given url.
     *
     * @private
     * @param {string} url - the url where to find the image to fetch
     * @returns {Deferred<string>}
     */
    _getBase64Image: function (url) {
        var def = $.Deferred();
        var xhr = new XMLHttpRequest();
        xhr.responseType = 'blob';
        xhr.onload = function () {
            var reader  = new FileReader();
            reader.onloadend = function () {
                def.resolve(reader.result);
            };
            reader.readAsDataURL(xhr.response);
        };
        xhr.open('GET', url);
        xhr.onerror = def.reject.bind(def);
        xhr.send();
        return def;
    },
    /**
     * Gets clearbit data with the given value. The fetched data is saved to
     * the "suggestions" attribute.
     *
     * @private
     * @param {string} value - the value whose associated clearbit data have to
     *                       be fetched
     * @returns {Deferred} resolved when the clearbit data has been fetched and
     *                     saved to the "suggestions" attribute
     */
    _getClearbitValues: function (value) {
        var self = this;
        var def = $.Deferred();
        $.ajax({
            url: _.str.sprintf('https://autocomplete.clearbit.com/v1/companies/suggest?query=%s', value),
            type: 'GET',
            dataType: 'json',
            success: function (suggestions) {
                self.suggestions = suggestions;
                def.resolve();
            }
        });
        return this._clearbitDropPrevious.add(def);
    },
    /**
     * Removes the dropdown showing the clearbit suggestions, if any.
     *
     * @private
     */
    _removeDropdown: function () {
        if (this.$dropdown) {
            this.$dropdown.remove();
            this.$dropdown = undefined;
        }
    },
    /**
     * Adds the <input/> element and prepares it. Note: the dropdown rendering
     * is handled outside of the rendering routine (but instead by reacting to
     * user input).
     *
     * @override
     * @private
     */
    _renderEdit: function () {
        this.$el.empty();
        // Prepare and add the input
        this._prepareInput().appendTo(this.$el);
    },
    /**
     * Shows the dropdown with the current clearbit suggestions. If one is
     * already opened, it removes the old one before rerendering the dropdown.
     *
     * @private
     */
    _showDropdown: function () {
        this._removeDropdown();
        if (this.suggestions.length > 0){
            this.$dropdown = $(QWeb.render('web_clearbit.dropdown', {
                suggestions: this.suggestions,
            }));
            this.$dropdown.appendTo(this.$el);
        }
    },
    /**
     * Selects the given company suggestions by notifying changes to the view
     * for the "name", "website" and "image" fields. This is of course intended
     * to work only with the "res.partner" form view.
     *
     * @private
     * @param {Object} - the clearbit company description
     */
    _selectCompany: function (company) {
        var self = this;
        $.when(company.logo ? this._getBase64Image(company.logo) : "").then(function (base64Image) {
            self.trigger_up('field_changed', {
                dataPointID: self.dataPointID,
                changes: {
                    name: company.name,
                    website: company.domain,
                    image: base64Image ? // base64Image equals "data:" if image not available on given url
                           base64Image.replace(/^data:image[^;]*;base64,?/, '') :
                           false,
                },
            });
        });
        this.$input.val(this._formatValue(company.name)); // update the input's value directly
        this._removeDropdown();
    },
    /**
     * Shows clearbit suggestions according to the given value.
     * Note: this method is debounced (@see init).
     *
     * @private
     * @param {string} value - the value whose associated clearbit data have to
     *                       be fetched
     */
    _suggestCompanies: function (value) {
        if (value.length > 0) {
            this._getClearbitValues(value).then(this._showDropdown.bind(this));
        } else {
            this._removeDropdown();
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override of FieldChar (called when the user is typing text)
     * Checks the <input/> value and shows clearbit suggestions according to
     * this value.
     *
     * @private
     */
    _onInput: function () {
        this._super.apply(this, arguments);
        if (this.record.data.company_type === 'company') {
            this._suggestCompanies(this.$input.val());
        }
    },
    /**
     * @override of FieldChar
     * Changes the "up" and "down" key behavior when the dropdown is opened (to
     * navigate through dropdown suggestions).
     * Triggered by keydown to execute the navigation multiple times when the
     * user keeps the "down" or "up" pressed.
     *
     * @private
     * @param {Event} e
     */
    _onKeydown: function (e) {
        switch (e.which) {
            case $.ui.keyCode.UP:
            case $.ui.keyCode.DOWN:
                if (!this.$dropdown) {
                    break;
                }
                e.preventDefault();
                var $suggestions = this.$dropdown.children();
                var $active = $suggestions.filter('.active');
                var $to;
                if ($active.length) {
                    $to = e.which === $.ui.keyCode.DOWN ?
                        $active.next() :
                        $active.prev();
                } else {
                    $to = $suggestions.first();
                }
                if ($to.length) {
                    $active.removeClass('active');
                    $to.addClass('active');
                }
                return;
        }
        this._super.apply(this, arguments);
    },
    /**
     * Called on keyup events to:
     * -> remove the suggestions dropdown when hitting the "escape" key
     * -> select the highlighted suggestion when hitting the "enter" key
     *
     * @private
     * @param {Event} e
     */
    _onKeyup: function (e) {
        switch (e.which) {
            case $.ui.keyCode.ESCAPE:
                e.preventDefault();
                this._removeDropdown();
                break;
            case $.ui.keyCode.ENTER:
                if (!this.$dropdown) {
                    break;
                }
                e.preventDefault();
                var $active = this.$dropdown.find('.active > .o_clearbit_suggestion');
                if (!$active.length) {
                    return;
                }
                this._selectCompany(this.suggestions[$active.data('index')]);
                break;
        }
    },
    /**
     * Called on mousedown event on a clearbit suggestion -> prevent default
     * action so that the <input/> element does not lose the focus.
     *
     * @private
     * @param {Event} e
     */
    _onMousedown: function (e) {
        e.preventDefault(); // prevent losing focus on suggestion click
    },
    /**
     * Called on focusout -> removes the suggestions dropdown.
     *
     * @private
     */
    _onFocusout: function () {
        this._removeDropdown();
    },
    /**
     * Called when hovering a suggestion in the dropdown -> sets it as active.
     *
     * @private
     * @param {Event} e
     */
    _onHoverDropdown: function (e) {
        this.$dropdown.find('.active').removeClass('active');
        $(e.currentTarget).parent().addClass('active');
    },
    /**
     * Called when a dropdown suggestion is clicked -> trigger_up changes for
     * some fields in the view (not only this <input/> one) with the associated
     * clearbit data (@see _selectCompany).
     *
     * @private
     * @param {Event} e
     */
    _onSuggestionClicked: function (e) {
        e.preventDefault();
        this._selectCompany(this.suggestions[$(e.currentTarget).data('index')]);
    },
});

field_registry.add('field_clearbit', FieldClearbit);

return FieldClearbit;
});
