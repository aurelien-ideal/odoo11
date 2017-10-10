odoo.define('web_grid.GridRenderer', function (require) {
"use strict";

var AbstractRenderer = require('web.AbstractRenderer');
var core = require('web.core');
var fieldUtils = require('web.field_utils');

var patch = require('snabbdom.patch');
var h = require('snabbdom.h');

var _t = core._t;

/**
 * The GridRenderer is the component that will render a grid view (obviously).
 * However, it is noteworthy to mention that it uses a rendering strategy
 * unusual in Odoo: it works with an external library, snabbdom, which is a
 * lightweight virtual dom implementation.
 */
return AbstractRenderer.extend({

    events: {
        'blur .o_grid_input': "_onGridInputBlur",
        'keydown .o_grid_input': "_onGridInputKeydown",
    },

    /**
     * @override
     * @param {Widget} parent
     * @param {Object} state
     * @param {Object} params
     */
    init: function (parent, state, params) {
        this._super.apply(this, arguments);
        this.canCreate = params.canCreate;
        this.fields = params.fields;
        this.noContentHelper = params.noContentHelper;
        this.editableCells = params.editableCells;
        this.cellWidget = params.cellWidget;
    },
    /**
     * @override
     */
    start: function () {
        // this is the vroot, the first patch call will replace the DOM node
        // itself instead of patching it in-place, so we're losing delegated
        // events if the state is the root node
        this._state = document.createElement('div');
        this.el.appendChild(this._state);
        return this._super();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} root
     */
    _convertToVNode: function (root) {
        var self = this;
        return h(root.tag, {'attrs': root.attrs}, _.map(root.children, function (child) {
                if (child.tag) {
                    return self._convertToVNode(child);
                 }
                 return child; // text node, no tag
         }));
    },
    /**
     * @private
     * @param {any[]} grid
     * @returns {{super: number, rows: {}, columns: {}}}
     */
    _computeTotals: function (grid) {
        var totals = {super: 0, rows: {}, columns: {}};
        for (var i = 0; i < grid.length; i++) {
            var row = grid[i];
            for (var j = 0; j < row.length; j++) {
                var cell = row[j];
                totals.super += cell.value;
                totals.rows[i] = (totals.rows[i] || 0) + cell.value;
                totals.columns[j] = (totals.columns[j] || 0) + cell.value;
            }
        }
        return totals;
    },
    /**
     * @private
     * @param {any} value
     * @returns {string}
     */
    _format: function (value) {
        if (value === undefined) {
            return '';
        }
        if (this.cellWidget) {
            return fieldUtils.format[this.cellWidget](value);
        }
        var cellField = this.fields[this.state.cellField];
        return fieldUtils.format[cellField.type](value, cellField);
    },
    /**
     * @private
     * @param {Object} cell
     * @param {boolean} cell.readonly
     * @returns {boolean}
     */
    _isCellReadonly: function (cell) {
        return !this.editableCells || cell.readonly;
    },
    /**
     * @private
     * @param {string} value
     * @returns {*}
     */
    _parse: function (value) {
        if (this.cellWidget) {
            return fieldUtils.parse[this.cellWidget](value);
        }
        var cellField = this.fields[this.state.cellField];
        return fieldUtils.parse[cellField.type](value, cellField);
    },
    /**
     * @private
     * @returns {Deferred}
     */
    _render: function () {
        var self = this;
        var vnode;

        if (_.isArray(this.state)) {
            // array of grid groups
            // get columns (check they're the same in all groups)
            if (!(_.isEmpty(this.state) || _.reduce(this.state, function (m, it) {
                return _.isEqual(m.cols, it.cols) && m;
            }))) {
                throw new Error(_t("The sectioned grid view can't handle groups with different columns sets"));
            }
            vnode = this._renderGroupedGrid();
        } else {
            vnode = this._renderUngroupedGrid();
        }

        this._state = patch(this._state, vnode);

        // need to debounce so grid can be rendered
        setTimeout(function () {
            var rowHeaders = self.el.querySelectorAll('tbody th:first-child div');
            for (var k = 0; k < rowHeaders.length; k++) {
                var header = rowHeaders[k];
                if (header.scrollWidth > header.clientWidth) {
                    $(header).addClass('overflow');
                }
            }
        }, 0);

        return $.when();
    },
    /**
     * @private
     * @param {Object} cell
     * @param {any} path
     * @returns {snabbdom}
     */
    _renderCell: function (cell, path) {
        var is_readonly = this._isCellReadonly(cell);

         // these are "hard-set" for correct grid behaviour
        var classmap = {
            o_grid_cell_container: true,
            o_grid_cell_empty: !cell.size,
            o_grid_cell_readonly: is_readonly,
        };
        // merge in class info from the cell
        // classes may be completely absent, _.each treats that as an empty array
        _.each(cell.classes, function (cls) {
            // don't allow overwriting initial values
            if (!(cls in classmap)) {
                classmap[cls] = true;
            }
        });

        return h('td', {class: {o_grid_current: cell.is_current}}, [
            this._renderCellContent(this._format(cell.value), is_readonly, classmap, path)
        ]);
    },
    /**
     * @private
     * @param {any} cell_value
     * @param {boolean} isReadonly
     * @param {any} classmap
     * @param {any} path
     * @returns {snabbdom}
     */
    _renderCellContent: function (cell_value, isReadonly, classmap, path) {
        return h('div', { class: classmap, attrs: {'data-path': path}}, [
            h('i.fa.fa-search-plus.o_grid_cell_information', {
                attrs: {
                    title: _t("See all the records aggregated in this cell")
                }
            }, []),
            this._renderCellInner(cell_value, isReadonly)
        ]);
    },
    /**
     * @private
     * @param {string} formattedValue
     * @param {boolean} isReadonly
     * @returns {snabbdom}
     */
    _renderCellInner: function (formattedValue, isReadonly) {
        if (isReadonly) {
            return h('div.o_grid_show', formattedValue);
        } else {
            return h('div.o_grid_input', {attrs: {contentEditable: "true"}}, formattedValue);
        }
    },
    /**
     * @private
     * @param {any} empty
     * @returns {snabbdom}
     */
    _renderEmptyWarning: function (empty) {
        if (!empty || !this.noContentHelper || !this.noContentHelper.children.length || !this.canCreate) {
            return [];
        }
        return h('div.o_grid_nocontent_container', [
                   h('div.oe_view_nocontent oe_edit_only',
                       _.map(this.noContentHelper.children, this._convertToVNode.bind(this))
                   )
               ]);
    },
    /**
     * @private
     * @param {Array<Array>} grid actual grid content
     * @param {Array<String>} groupFields
     * @param {Array} path object path to `grid` from the object's state
     * @param {Array} rows list of row keys
     * @param {Object} totals row-keyed totals
     * @returns {snabbdom[]}
     */
    _renderGridRows: function (grid, groupFields, path, rows, totals) {
        var self = this;
        return _.map(grid, function (row, rowIndex) {
            var rowValues = [];
            for (var i = 0; i < groupFields.length; i++) {
                var row_field = groupFields[i];
                var value = rows[rowIndex].values[row_field];
                rowValues.push(value);
            }
            var rowKey = _.map(rowValues, function (v) {
                return v[0];
            }).join('|');

            return h('tr', {key: rowKey}, [
                h('th', {}, [
                    h('div', _.map(rowValues, function (v) {
                        var label = v ? v[1] : _t('Unknown');
                        var klass = v ? '' : 'o_grid_text_muted';
                        return h('div', {attrs: {title: label, class: klass}}, label);
                    }))
                ])
            ].concat(_.map(row, function (cell, cell_index) {
                return self._renderCell(cell, path.concat([rowIndex, cell_index]).join('.'));
            }), [h('td.o_grid_total', self._format(totals[rowIndex]))]));
        });
    },
    /**
     * @private
     * @returns {snabbdom}
     */
    _renderGroupedGrid: function () {
        var self = this;
        var columns = this.state.length ? this.state[0].cols : [];
        var superTotals = this._computeTotals(
            _.flatten(_.pluck(this.state, 'grid'), true));
        var vnode = this._renderTable(columns, superTotals.columns);
        var gridBody = vnode.children[0].children;
        for (var n = 0; n < this.state.length; n++) {
            var grid = this.state[n];

            var totals = this._computeTotals(grid.grid);
            var rows = this._renderGridRows(
                grid.grid || [],
                this.state.groupBy.slice(1),
                [n, 'grid'],
                grid.rows || [],
                totals.rows
            );
            gridBody.push(
                h('tbody', {class: {o_grid_section: true}}, [
                    h('tr', [
                        h('th', {}, [
                            (grid.__label || [])[1] || "\u00A0"
                        ])
                    ].concat(
                        _(columns).map(function (column, column_index) {
                            return h('td', {class: {
                                o_grid_current: column.is_current,
                            }}, self._format(totals.columns[column_index]));
                        }),
                        [h('td.o_grid_total', [
                            self._format(totals.super)
                        ])]
                    ))
                ].concat(rows)
            ));
        }
        return vnode;
    },
    /**
     * Generates the header and footer for the grid's table. If
     * totals and super_total are provided they will be formatted and
     * inserted into the table footer, otherwise the cells will be left empty
     *
     * @private
     * @param {Array} columns
     * @param {Object} [totals]
     * @param {Number} [super_total]
     * @param {boolean} [empty=false]
     * @returns {snabbdom}
     */
    _renderTable: function (columns, totals, super_total, empty) {
        var self = this;
        var col_field = this.state.colField;
        return h('div.o_view_grid', [
            h('table.table.table-condensed.table-responsive.table-striped', [
                h('thead', [
                    h('tr', [
                        h('th.o_grid_title_header'),
                    ].concat(
                        _.map(columns, function (column) {
                            return h('th', {class: {o_grid_current: column.is_current}},
                                column.values[col_field][1]
                            );
                        }),
                        [h('th.o_grid_total', _t("Total"))]
                    ))
                ]),
                h('tfoot', [
                    h('tr', [
                        h('td', totals ? _t("Total") : [])
                    ].concat(
                        _.map(columns, function (column, column_index) {
                            var cell_content = !totals ? []
                                : self._format(totals[column_index]);
                            return h('td', {class: {
                                o_grid_current: column.is_current,
                            }}, cell_content);
                        }),
                        [h('td', !super_total ? [] : self._format(super_total))]
                    ))
                ]),
            ])
        ].concat(this._renderEmptyWarning(empty)));
    },
    /**
     * @private
     * @returns {snabbdom}
     */
    _renderUngroupedGrid: function () {
        var vnode;
        var columns = this.state.cols;
        var rows = this.state.rows;
        var grid = this.state.grid;

        var totals = this._computeTotals(grid);
        vnode = this._renderTable(columns, totals.columns, totals.super, !grid.length);
        vnode.children[0].children.push(
            h('tbody',
                this._renderGridRows(
                    grid,
                    this.state.groupBy,
                    ['grid'],
                    rows,
                    totals.rows
                ).concat(_.times(Math.max(5 - rows.length, 0), function () {
                    return h('tr.o_grid_padding', [
                        h('th', {}, "\u00A0")
                    ].concat(
                        _.map(columns, function (column) {
                            return h('td', {class: {o_grid_current: column.is_current}}, []);
                        }),
                        [h('td.o_grid_total', [])]
                    ));
                }))
            )
        );
        return vnode;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} e
     */
    _onGridInputBlur: function (e) {
        var $target = $(e.target);
        var value;

        try {
            value = this._parse(e.target.textContent.trim());
            $target.removeClass('has-error');
        } catch (_) {
            $target.addClass('has-error');
            return;
        }

        // path should be [path, to, grid, 'grid', row_index, col_index]
        var cell_path = $target.parent().attr('data-path').split('.');
        var grid_path = cell_path.slice(0, -3);
        var row_path = grid_path.concat(['rows'], cell_path.slice(-2, -1));
        var col_path = grid_path.concat(['cols'], cell_path.slice(-1));
        this.trigger_up('cell_edited', {
            cell_path: cell_path,
            row_path: row_path,
            col_path: col_path,
            value: value,
        });
    },
    /**
     * @private
     * @param {KeyboardEvent} e
     */
    _onGridInputKeydown: function (e) {
        // suppress [return]
        switch (e.which) {
        case $.ui.keyCode.ENTER:
            e.preventDefault();
            e.stopPropagation();
            break;
        }
    },
});

});
