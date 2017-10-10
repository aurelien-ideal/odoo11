odoo.define('website_version.tour', function (require) {
    'use strict';

    var base = require('web_editor.base');
    var core = require('web.core');
    var tour = require("web_tour.tour");

    var _t = core._t;

    tour.register("versioning", {
        wait_for: base.ready()
    }, [{ //1.
        content:  _t("You can create a version for every page of your website."),
        position: "bottom",
        trigger:  'a#version-menu-button',
    }, {
        content:  _t("Click on New version"),
        position: 'bottom',
        trigger:  'a[data-action="duplicate_version"]',
    }, {
        content:  _t("Give a clever name to retrieve it easily."),
        extra_trigger:  'button.btn-primary.o_create',
        trigger:  'input.o_version_name[type="text"]',
        run: 'text Test',
    }, {
        content:  _t("Validate the version name"),
        trigger:  'button.btn-primary.o_create',
    }, {
        content:  _t("Confirm"),
        extra_trigger:  'html:not(:has(.modal input.form-control[type=text])) .modal',
        trigger:  'button.o_confirm',
    }, {
        content:  _t("All the modifications you will do, will be saved in this version. Drag the Cover block and drop it in your page."),
        extra_trigger:  'html:not(:has(a[data-action="edit"]:visible)) #snippet_structure .oe_snippet .oe_snippet_thumbnail',
        trigger:  "#snippet_structure .oe_snippet:eq(1) .oe_snippet_thumbnail",
        position: "bottom",
        run: "drag_and_drop",
    }, {
        content:  _t("Click in the content text and start editing it."),
        extra_trigger:  '.oe_overlay_options .oe_options',
        trigger:  '#wrapwrap .s_text_block_image_fw h2',
        position: 'top',
        run: 'text Here, a customized text',
    }, {
        content:  _t("Customize any block through this menu. Try to change the background of the banner."),
        extra_trigger:  "#wrapwrap .s_text_block_image_fw h2:not(:containsExact(\"Headline\"))",
        trigger:  '.oe_overlay_options .oe_options',
        position: 'top',
    }, {
        content:  _t("Drag the <em>'Features'</em> block and drop it below the banner."),
        trigger:  "#snippet_structure .oe_snippet:eq(6) .oe_snippet_thumbnail",
        position: "bottom",
        run: "drag_and_drop",
    }, {
        content:  _t("Publish your page by clicking on the <em>'Save'</em> button."),
        extra_trigger:  '.oe_overlay_options .oe_options',
        trigger:  'button[data-action=save]',
        position: "bottom",
    }, { //2.
        content:  _t("Well done, you created a version of your homepage. Now we will publish your version in production."),
        trigger:  'a#version-menu-button',
    }, {
        content:  _t("Click on Publish Version"),
        position: 'left',
        trigger:  'a[data-action="publish_version"]',
    }, {
        content:  _t("Click on Publish button"),
        trigger:  'button.o_confirm',
        position: 'right',
    }, {
        content:  _t("Confirm"),
        position: 'right',
        trigger:  'button.o_confirm[data-dismiss]',
    }, { //3.
        content:  _t("Now we will delete the version you have just published."),
        position: "bottom",
        trigger:  'a#version-menu-button',
    }, {
        content:  _t("Delete Version Test"),
        position: "bottom",
        trigger:  'li > a[data-action="delete_version"]:last',
    }, {
        content:  _t("Click on delete version button"),
        position: 'bottom',
        trigger:  '.modal-footer:has(.cancel) button.o_confirm',
    }, {
        content:  _t("Confirm. Felicitation, you are now able to edit and manage your versions."),
        position: 'right',
        trigger:  '.modal-footer:not(:has(.cancel)) button.o_confirm[data-dismiss]',
    }]);
});
