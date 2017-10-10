odoo.define('web_studio.EditorMixin', function() {
"use strict";

return {
    /**
     * Highlight the nearest hook regarding the position and remove the
     * highlighto on other elements.
     *
     * @param {JQuery} $helper - the helper being dragged
     * @param {Object} position - {pageX: x, pageY: y}
     */
    highlightNearestHook: function ($helper, position) {
        this.$('.o_web_studio_nearest_hook').removeClass('o_web_studio_nearest_hook');
        // to be implemented by each editor
    },
    /*
     * Set the style and the corresponding event on a selectable node (fields,
     * groups, etc.) of the editor
     */
    setSelectable: function ($el) {
        var self = this;
        $el.click(function() {
            self.unselectedElements();
            $(this).addClass('o_clicked');
        })
        .mouseover(function(event) {
            $(this).addClass('o_web_studio_hovered');
            event.stopPropagation();
        })
        .mouseout(function(event) {
            $(this).removeClass('o_web_studio_hovered');
            event.stopPropagation();
        });
    },
    unselectedElements: function () {
        this.selected_node_id = false;
        var $el = this.$('.o_clicked');
        $el.removeClass('o_clicked');
        if ($el.find('.blockUI')) {
            $el.find('.blockUI').parent().unblock();
        }
    },
};

});
