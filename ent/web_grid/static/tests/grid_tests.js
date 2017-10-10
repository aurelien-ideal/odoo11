odoo.define('web_grid.grid_tests', function (require) {
"use strict";

var concurrency = require('web.concurrency');
var GridView = require('web_grid.GridView');
var testUtils = require('web.test_utils');

var createView = testUtils.createView;

QUnit.module('Views', {
    beforeEach: function () {
        this.data = {
            'analytic.line': {
                fields: {
                    project_id: {string: "Project", type: "many2one", relation: "project"},
                    task_id: {string: "Task", type: "many2one", relation: "task"},
                    date: {string: "Date", type: "date"},
                    unit_amount: {string: "Unit Amount", type: "float"},
                },
                records: [
                    {id: 1, project_id: 31, date: "2017-01-24", unit_amount: 2.5},
                    {id: 2, project_id: 31, task_id: 1, date: "2017-01-25", unit_amount: 2},
                    {id: 3, project_id: 31, task_id: 1, date: "2017-01-25", unit_amount: 5.5},
                    {id: 4, project_id: 31, task_id: 1, date: "2017-01-30", unit_amount: 10},
                    {id: 5, project_id: 142, task_id: 12, date: "2017-01-31", unit_amount: 3.5},
                ]
            },
            project: {
                fields: {
                    name: {string: "Project Name", type: "char"}
                },
                records: [
                    {id: 31, display_name: "P1"},
                    {id: 142, display_name: "Webocalypse Now"},
                ]
            },
            task: {
                fields: {
                    name: {string: "Task Name", type: "char"},
                    project_id: {string: "Project", type: "many2one", relation: "project"},
                },
                records: [
                    {id: 1, display_name: "BS task", project_id: 31},
                    {id: 12, display_name: "Another BS task", project_id: 142},
                    {id: 54, display_name: "yet another task", project_id: 142},
                ]
            },
        };
        this.arch = '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                    '<button string="Action" type="action" name="action_name"/>' +
                    '<empty>' +
                        '<p class="oe_view_nocontent_create">' +
                            'Click to add projects and tasks' +
                        '</p>' +
                        '<p>you will be able to register your working hours on the given task</p>' +
                        '<p><a href="some-link"><img src="some-image" alt="alt text"/></a></p>' +
                    '</empty>' +
                '</grid>';
        this.archs = {
            'analytic.line,23,form': '<form string="Add a line"><group><group>' +
                                  '<field name="project_id"/>' +
                                  '<field name="task_id"/>' +
                                  '<field name="date"/>' +
                                  '<field name="unit_amount" string="Time spent"/>' +
                                '</group></group></form>',
        };
    }
}, function () {
    QUnit.module('GridView');

    QUnit.test('basic grid view', function (assert) {
        assert.expect(17);
        var done = assert.async();

        var grid = createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function (route) {
                if (route === 'some-image') {
                    return $.when();
                }
                return this._super.apply(this, arguments);
            },
        });

        return concurrency.delay(0).then(function () {
            assert.ok(grid.$('table').length, "should have rendered a table");
            assert.strictEqual(grid.$('div.o_grid_cell_container').length, 14,
                "should have 14 cells");
            assert.strictEqual(grid.$('div.o_grid_input:contains(02:30)').length, 1,
                "should have correctly parsed a float_time");
            assert.strictEqual(grid.$('div.o_grid_input:contains(00:00)').length, 12,
                "should have correctly parsed another float_time");

            assert.ok(grid.$buttons.find('button.grid_arrow_previous').is(':visible'),
                "previous button should be visible");
            assert.ok(grid.$buttons.find('button.grid_arrow_range[data-name="week"]').hasClass('active'),
                "current range is shown as active");

            assert.strictEqual(grid.$('tfoot td:contains(02:30)').length, 1, "should display total in a column");
            assert.strictEqual(grid.$('tfoot td:contains(00:00)').length, 5, "should display totals, even if 0");

            grid.$buttons.find('button.grid_arrow_next').click();
            return concurrency.delay(0);
        }).then(function () {
            assert.ok(grid.$('div.o_grid_cell_container').length, "should not have any cells");
            assert.ok(grid.$('th div:contains(P1)').length,
                "should have rendered a cell with project name");
            assert.ok(grid.$('th div:contains(BS task)').length,
                "should have rendered a cell with task name");
            assert.notOk(grid.$('.o_grid_nocontent_container p:contains(Click to add projects and tasks)').length,
                "should not have rendered a no content helper");

            assert.notOk(grid.$('td.o_grid_current').length, "should not have any cell marked current");
            grid.$buttons.find('button.grid_arrow_next').click();

            return concurrency.delay(0);
        }).then(function () {
            assert.ok(grid.$('.o_grid_nocontent_container p:contains(Click to add projects and tasks)').length,
                "should have rendered a no content helper");
            assert.strictEqual(grid.$('.o_grid_nocontent_container p a img').length, 1,
                "should have rendered a no content helper with an image in a link");

            assert.notOk(grid.$('div.o_grid_cell_container').length, "should not have any cell");

            var emptyTd = 0;
            grid.$('tfoot td').each(function () {
                if ($(this).text() === '') {
                    emptyTd++;
                }
            });
            assert.strictEqual(emptyTd, 8, "8 totals cells should be empty");
            grid.destroy();
            done();
        });

    });

    QUnit.test('basic grouped grid view', function (assert) {
        assert.expect(33);
        var done = assert.async();
        var nbReadGridDomain = 0;
        var nbReadGroup = 0;
        var nbReadGrid = 0;

        this.data['analytic.line'].records.push([
            {id: 6, project_id: 142, task_id: 12, date: "2017-01-31", unit_amount: 3.5},
        ]);

        this.arch = '<grid string="Timesheet By Project" adjustment="object" adjust_name="adjust_grid">' +
                '<field name="project_id" type="row" section="1"/>' +
                '<field name="task_id" type="row"/>' +
                '<field name="date" type="col">' +
                    '<range name="week" string="Week" span="week" step="day"/>' +
                    '<range name="month" string="Month" span="month" step="day"/>' +
                '</field>'+
                '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '<empty>' +
                    '<p class="oe_view_nocontent_create">' +
                        'Click to add projects and tasks' +
                    '</p>' +
                    '<p>you will be able to register your working hours on the given task</p>' +
                    '<p><a href="some-link"><img src="some-image" alt="alt text"/></a></p>' +
                '</empty>' +
            '</grid>';

        var grid = createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function (route, args) {
                if (route === 'some-image') {
                    return $.when();
                } else if (args.method === 'read_grid_domain') {
                    nbReadGridDomain++;
                } else if (args.method === 'read_group') {
                    assert.strictEqual(args.kwargs.groupby.length, 1,
                        "should read group on the section (project_id)");
                    assert.strictEqual(args.kwargs.groupby[0], 'project_id',
                        "should read group on the section (project_id)");
                    nbReadGroup++;
                } else if (args.method === 'read_grid') {
                    nbReadGrid++;
                }
                return this._super.apply(this, arguments);
            },
        });

        return concurrency.delay(0).then(function () {
            assert.ok(grid.$('table').length, "should have rendered a table");
            assert.strictEqual(nbReadGridDomain, 1, "should have read the grid domain");
            assert.strictEqual(nbReadGridDomain, 1, "should have read group");
            assert.strictEqual(nbReadGrid, 2, "should have read one grid by group");
            assert.strictEqual(grid.$('.o_grid_section').length, 2, "should have one section by project");

            // first section
            assert.strictEqual(grid.$('.o_grid_section:eq(0) th:contains(P1)').length, 1,
                "first section should be for project P1");
            assert.strictEqual(grid.$('.o_grid_section:eq(0) div.o_grid_cell_container').length, 14,
                "first section should have 14 cells");
            assert.strictEqual(grid.$('.o_grid_section:eq(0) th:contains(Unknown)').length, 1,
                "first section should have a row without task");
            assert.strictEqual(grid.$('.o_grid_section:eq(0) th:contains(BS task)').length, 1,
                "first section should have a row for BS task");

            assert.strictEqual(grid.$('.o_grid_section:eq(0) tr:eq(2) div.o_grid_input:contains(02:30)').length, 1,
                "should have correctly parsed a float_time for cell without task");
            assert.strictEqual(grid.$('.o_grid_section:eq(0) div.o_grid_input:contains(00:00)').length, 12,
                "should have correctly parsed another float_time");

            // second section
            assert.strictEqual(grid.$('.o_grid_section:eq(1) th:contains(Webocalypse Now)').length, 1,
                "second section should be for project Webocalypse Now");
            assert.strictEqual(grid.$('.o_grid_section:eq(1) th:contains(Another BS task)').length, 0,
                "first section should be empty");
            assert.strictEqual(grid.$('.o_grid_section:eq(1) div.o_grid_cell_container').length, 0,
                "second section should be empty");

            assert.ok(grid.$buttons.find('button.grid_arrow_previous').is(':visible'),
                "previous button should be visible");
            assert.ok(grid.$buttons.find('button.grid_arrow_range[data-name="week"]').hasClass('active'),
                "current range is shown as active");

            assert.strictEqual(grid.$('tfoot td:contains(02:30)').length, 1, "should display total in a column");
            assert.strictEqual(grid.$('tfoot td:contains(00:00)').length, 5, "should display totals, even if 0");

            grid.$buttons.find('button.grid_arrow_next').click();
            return concurrency.delay(0);
        }).then(function () {
            assert.strictEqual(nbReadGridDomain, 2, "should have read the grid domain again");
            assert.strictEqual(nbReadGridDomain, 2, "should have read group again");
            assert.strictEqual(nbReadGrid, 4, "should have read one grid by group again");

            assert.ok(grid.$('div.o_grid_cell_container').length, "should not have any cells");
            assert.ok(grid.$('th:contains(P1)').length,
                "should have rendered a cell with project name");
            assert.ok(grid.$('th div:contains(BS task)').length,
                "should have rendered a cell with task name");
            assert.strictEqual(grid.$('.o_grid_section:eq(1) th:contains(Another BS task)').length, 1,
                "first section should have a row for Another BS task");
            assert.strictEqual(grid.$('.o_grid_section:eq(1) div.o_grid_cell_container').length, 7,
                "second section should have 7 cells");
            grid.$buttons.find('button.grid_arrow_next').click();

            return concurrency.delay(0);
        }).then(function () {
            assert.strictEqual(grid.$('.o_grid_nocontent_container').length, 0,
                "should not have rendered a no content helper in grouped");
            grid.destroy();
            done();
        });
    });

    QUnit.test('create analytic lines', function (assert) {
        assert.expect(7);
        var done = assert.async();
        this.data['analytic.line'].fields.date.default = "2017-02-25";

        var grid = createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            currentDate: "2017-02-25",
            viewOptions: {
                views: [[23, 'form']],
            },
            archs: this.archs,
            mockRPC: function (route, args) {
                if (args.method === 'create') {
                    assert.strictEqual(args.args[0].date, "2017-02-25",
                        "default date should be current day");
                }
                return this._super(route, args);
            },
        });

        return concurrency.delay(0).then(function () {
            assert.strictEqual(grid.$('.o_grid_nocontent_container').length, 0,
                "should not have rendered a no content helper");

            assert.strictEqual(grid.$('div.o_grid_cell_container').length, 0, "should not have any cells");
            assert.notOk($('div.modal').length, "should not have any modal open");
            grid.$buttons.find('.o_grid_button_add').click();

            assert.ok($('div.modal').length, "should have opened a modal");

            // input a project and a task
            for (var i = 0; i < 2; i++) {
                $('.modal .o_field_many2one input').eq(i).click();
                $('.modal .o_field_many2one input').eq(i).autocomplete('widget').find('a').first().click();
            }

            // input unit_amount
            $('.modal input').eq(3).val("4").trigger('input');

            // save
            $('.modal .modal-footer button.btn-primary').click();
            return concurrency.delay(0);
        }).then(function () {
            assert.strictEqual(grid.$('div.o_grid_cell_container').length, 7,
                "should have 7 cell containers (1 for each day)");

            assert.strictEqual(grid.$('td.o_grid_total:contains(4:00)').length, 1,
                "should have a total of 4:00");

            grid.destroy();
            done();
        });
    });

    QUnit.test('create analytic lines on grouped grid view', function (assert) {
        assert.expect(4);
        var done = assert.async();
        this.data['analytic.line'].fields.date.default = "2017-02-25";

        var grid = createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"  section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            currentDate: "2017-02-25",
            viewOptions: {
                views: [[23, 'form']],
            },
            domain: [['date', '>', '2014-09-09']],
            archs: this.archs,
            mockRPC: function (route, args) {
                if (args.method === 'read_group') {
                    assert.deepEqual(args.kwargs.domain[3], ['date', '>', '2014-09-09'],
                        "the action domain should always be given");
                }
                if (args.method === 'create') {
                    assert.strictEqual(args.args[0].date, "2017-02-25",
                        "default date should be current day");
                }
                return this._super(route, args);
            },
        });

        return concurrency.delay(0).then(function () {
            grid.$buttons.find('.o_grid_button_add').click();
            assert.ok($('div.modal').length, "should have opened a modal");
            // input a project and a task
            for (var i = 0; i < 2; i++) {
                $('.modal .o_field_many2one input').eq(i).click();
                $('.modal .o_field_many2one input').eq(i).autocomplete('widget').find('a').first().click();
            }
            // input unit_amount
            $('.modal input').eq(3).val("4").trigger('input');
            // save
            $('.modal .modal-footer button.btn-primary').click();

            grid.destroy();
            done();
        });

    });

    QUnit.test('switching active range', function (assert) {
        assert.expect(6);
        var done = assert.async();
        this.data['analytic.line'].fields.date.default = "2017-02-25";

        var grid = createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            currentDate: "2017-02-25",
        });

        return concurrency.delay(0).then(function () {
            assert.strictEqual(grid.$('thead th:not(.o_grid_title_header)').length, 8,
                "should have 8 columns (1 for each day + 1 for total)");
            assert.ok(grid.$buttons.find('button.grid_arrow_range[data-name="week"]').hasClass('active'),
                "current range is shown as active");
            assert.notOk(grid.$buttons.find('button.grid_arrow_range[data-name="month"]').hasClass('active'),
                "month range is not active");

            grid.$buttons.find('button[data-name=month]').click();

            return concurrency.delay(0);
        }).then(function () {

            assert.strictEqual(grid.$('thead th:not(.o_grid_title_header)').length, 29,
                "should have 29 columns (1 for each day + 1 for total)");
            assert.ok(grid.$buttons.find('button.grid_arrow_range[data-name="month"]').hasClass('active'),
                "month range is shown as active");
            assert.notOk(grid.$buttons.find('button.grid_arrow_range[data-name="week"]').hasClass('active'),
                "week range is not active");

            grid.destroy();
            done();
        });

    });

    QUnit.test('clicking on the info icon on a cell triggers a do_action', function (assert) {
        assert.expect(3);
        var done = assert.async();

        var domain;

        var grid = createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function () {
                return this._super.apply(this, arguments).then(function (result) {
                    domain = result.grid[0][2].domain;
                    return result;
                });
            }
        });

        return concurrency.delay(0).then(function () {
            assert.strictEqual(grid.$('i.o_grid_cell_information').length, 14,
                "should have 14 icons to open cell info");

            testUtils.intercept(grid, 'do_action', function (event) {
                var action = event.data.action;

                assert.deepEqual(action.domain, domain, "should trigger a do_action with correct values");
                assert.strictEqual(action.name, "P1: BS task",
                    "should have correct action name");
            });
            grid.$('i.o_grid_cell_information').eq(2).click();

            grid.destroy();
            done();
        });
    });

    QUnit.test('editing a value', function (assert) {
        assert.expect(13);
        var done = assert.async();

        var grid = createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            viewOptions: {
                context: {some_value: 2},
            },
            mockRPC: function (route, args) {
                if (args.method === 'search') {
                    return $.when([1, 2, 3, 4, 5]);
                }
                return this._super.apply(this, arguments);
            },
            intercepts: {
                execute_action: function (event) {
                    if (event.data.action_data.type === 'action') {
                        assert.strictEqual(event.data.env.model, 'analytic.line',
                            'should call with correct model in env');
                        assert.deepEqual(event.data.env.context, {some_value: 2},
                            'should call with correct context in env');
                        assert.deepEqual(event.data.env.resIDs, [1, 2, 3, 4, 5],
                            'should call with correct resIDs in env');
                    } else if (event.data.action_data.type === 'object') {
                        assert.strictEqual(event.data.env.model, 'analytic.line',
                            'should call with correct model in env');
                        assert.deepEqual(event.data.env.context, {some_value: 2},
                            'should call with correct context in env');
                        assert.notOk('resIDs' in event.data.env,
                            'should not have set resIDs in env');
                        grid._rpc({
                                model: 'analytic.line',
                                method: 'adjust_grid',
                                kwargs: event.data.action_data,
                            })
                            .then(event.data.on_success)
                            .fail(event.data.on_fail);
                    }
                },
            },
        });

        return concurrency.delay(0).then(function () {
            var $input = grid.$('.o_grid_cell_container:eq(0) div.o_grid_input');

            assert.notOk($input.hasClass('has-error'),
                "input should not show any error at start");
            $input.click();
            $input.focus();
            var selection = window.getSelection();
            assert.strictEqual($(selection.focusNode).closest(".o_grid_input")[0], $input[0],
                "the text in the cell is focused");
            assert.strictEqual(selection.anchorOffset, 0,
                "selection starts at index 0");
            /**
             * The next assertion is browser dependent. Indeed Firefox and
             * Chrome implement two working `window.getSelection` but with
             * different return results.
             *
             * On Chrome, selecting the whole content of a node with an unique
             * text node thanks to the `Range.selectNodeContents` function
             * creates a Range element whose reference is the text node and the
             * selection end value is the text node length.
             * On Firefox, doing the same operation creates a Range element
             * whose reference is the parent node and the selection end value
             * is 1 (saying that one whole text node is selected).
             *
             * Note that the test could just check that the selection end is
             * greater than 1 (checking that something is selected), but this
             * problem was worth mentioning and the test is maybe more correct
             * and explicit this way.
             */
            assert.strictEqual(selection.focusOffset, selection.focusNode === $input[0] ? 1 : 5,
                "selection ends at the text end (so the 00:00 text is selected)");

            $input.text('abc');
            $input.focusout();

            assert.ok($input.hasClass('has-error'),
                "input should be formatted to show that there was an error");

            $input.text('8.5');
            $input.focusout();

            assert.notOk($input.hasClass('has-error'),
                "input should not be formatted like there is an error");

            assert.strictEqual($input.text(), "08:30",
                "text should have been properly parsed/formatted");

            grid.$buttons.find('button:contains("Action")').click()

            grid.destroy();
            done();
        });
    });

});
});
