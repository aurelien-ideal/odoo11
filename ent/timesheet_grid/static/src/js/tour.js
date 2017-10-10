odoo.define('timesheet.tour', function(require) {
"use strict";

var core = require('web.core');
var tour = require('web_tour.tour');

var _t = core._t;

tour.register('timesheet_tour', {
    url: "/web",
}, [tour.STEPS.MENU_MORE, {
    trigger: '.o_app[data-menu-xmlid="hr_timesheet.timesheet_menu_root"], .oe_menu_toggler[data-menu-xmlid="hr_timesheet.timesheet_menu_root"]',
    content: _t('Track your timesheets to invoice easily, or control costs. <i>It starts here.</i>'),
    position: 'bottom',
}, {
    trigger: '.o_grid_button_add',
    content: _t('Let\'s create your first timesheet entry.'),
    position: 'right',
    width: 200,
}, {
    trigger: ".modal-body .o_timesheet_tour_project_name",
    content: _t('Choose a <b>project name</b>. (e.g. name of a customer, or product)'),
    position: "right",
    run: function (actions) {
        actions.auto();
    },
}, {
    trigger: ".modal-body .o_timesheet_tour_task_name",
    content: _t('Use tasks to track the different type of activities. (e.g. Graphic Design, Programming, Project Management)'),
    position: "right",
    run: function (actions) {
        actions.auto(".modal-footer .btn-default");
    },
}, {
    trigger: '.o_grid_input',
    content: _t('Set the number of hours done on this project, for every day of the week. (e.g. 1.5 or 1:30)'),
    position: 'top',
    run: function (actions) {
        actions.text("4", this.$anchor);
    },
}, {
    trigger: '.grid_arrow_range[data-name="month"]',
    content: _t('Easily switch to the monthly or daily view to control your time'),
    position: 'right',
}]);

});
