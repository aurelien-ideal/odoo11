# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
from odoo.tools import float_compare, float_round
from odoo.addons import decimal_precision as dp


class MrpProductionWorkcenterLine(models.Model):
    _inherit = "mrp.workorder"

    check_ids = fields.One2many('quality.check', 'workorder_id')
    skipped_check_ids = fields.One2many('quality.check', 'workorder_id', domain=[('quality_state', '=', 'none')])
    finished_product_check_ids = fields.Many2many('quality.check', compute='_compute_finished_product_check_ids')
    quality_check_todo = fields.Boolean(compute='_compute_check')
    quality_check_fail = fields.Boolean(compute='_compute_check')
    quality_alert_ids = fields.One2many('quality.alert', 'workorder_id')
    quality_alert_count = fields.Integer(compute="_compute_quality_alert_count")

    current_quality_check_id = fields.Many2one('quality.check', "Current Quality Check", store=True)

    # QC-related fields
    allow_producing_quantity_change = fields.Boolean('Allow Changes to Producing Quantity', default=True)
    component_id = fields.Many2one('product.product', compute='_compute_component_id', readonly=True)
    component_tracking = fields.Selection(related='component_id.tracking')
    component_remaining_qty = fields.Float('Remaining Quantity for Component', compute='_compute_component_id', readonly=True,digits=dp.get_precision('Product Unit of Measure'))
    component_uom_id = fields.Many2one(related='component_id.uom_id')
    control_date = fields.Datetime(related='current_quality_check_id.control_date')
    is_first_step = fields.Boolean('Is First Step')
    is_last_step = fields.Boolean('Is Last Step')
    is_last_lot = fields.Boolean('Is Last lot', compute='_compute_is_last_lot')
    lot_id = fields.Many2one(related='current_quality_check_id.lot_id')
    move_line_id = fields.Many2one(related='current_quality_check_id.move_line_id')
    measure = fields.Float(related='current_quality_check_id.measure')
    measure_success = fields.Selection(related='current_quality_check_id.measure_success')
    norm_unit = fields.Char(related='current_quality_check_id.norm_unit')
    note = fields.Html(related='current_quality_check_id.note')
    picture = fields.Binary(related='current_quality_check_id.picture')
    skip_completed_checks = fields.Boolean('Skip Completed Checks', readonly=True)
    quality_state = fields.Selection(related='current_quality_check_id.quality_state')
    qty_done = fields.Float(related='current_quality_check_id.qty_done')
    test_type = fields.Char('Test Type', compute='_compute_component_id', readonly=True)
    user_id = fields.Many2one(related='current_quality_check_id.user_id')
    worksheet_page = fields.Integer('Worksheet page')

    @api.depends('qty_producing', 'qty_remaining')
    def _compute_is_last_lot(self):
        for wo in self:
            wo.is_last_lot = wo.qty_producing >= wo.qty_remaining

    @api.depends('check_ids')
    def _compute_finished_product_check_ids(self):
        for wo in self:
            wo.finished_product_check_ids = wo.check_ids.filtered(lambda c: c.finished_product_sequence == wo.qty_produced)

    @api.depends('current_quality_check_id', 'qty_producing')
    def _compute_component_id(self):
        for wo in self:
            if wo.current_quality_check_id.point_id:
                wo.component_id = wo.current_quality_check_id.point_id.component_id
                wo.test_type = wo.current_quality_check_id.point_id.test_type
            elif wo.current_quality_check_id.component_id:
                wo.component_id = wo.current_quality_check_id.component_id
                wo.test_type = 'register_consumed_materials'
            else:
                wo.test_type = ''
            if wo.test_type == 'register_consumed_materials' and wo.quality_state == 'none':
                moves = wo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id == wo.component_id)
                move = moves[0]
                lines = wo.active_move_line_ids.filtered(lambda l: l.move_id in moves)
                completed_lines = lines.filtered(lambda l: l.lot_id) if wo.component_tracking != 'none' else lines
                wo.component_remaining_qty = float_round(sum(moves.mapped('unit_factor')) * wo.qty_producing - sum(completed_lines.mapped('qty_done')), precision_rounding=move.product_uom.rounding)

    def action_back(self):
        self.ensure_one()
        if self.is_user_working and self.working_state != 'blocked':
            self.button_pending()

    def _next(self, state='pass'):
        self.ensure_one()
        if self.qty_producing <= 0 or self.qty_producing > self.qty_remaining:
            raise UserError(_('Please ensure the quantity to produce is nonnegative and does not exceed the remaining quantity.'))
        if self.test_type == 'picture' and not self.picture:
            raise UserError(_('Please upload a picture.'))
        elif self.test_type == 'register_consumed_materials':
            # Form validation
            if self.component_tracking != 'none' and not self.lot_id:
                raise UserError(_('Please enter a Lot/SN.'))
            if self.component_tracking == 'none' and self.qty_done <= 0:
                raise UserError(_('Please enter a positive quantity.'))
            # Get the move lines associated with our component
            moves = self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id == self.component_id)
            move = moves[0]
            lines_without_lots = self.active_move_line_ids.filtered(lambda l: l.move_id in moves and not l.lot_id)
            # Compute the theoretical quantity for the current production
            self.component_remaining_qty -= float_round(self.qty_done, precision_rounding=move.product_uom.rounding)
            # Assign move line to quality check if necessary
            if not self.move_line_id:
                if self.component_tracking == 'none':
                    self.move_line_id = self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'lot_id': False,
                        'product_uom_qty': 0.0,
                        'product_uom_id': move.product_uom.id,
                        'qty_done': float_round(self.qty_done, precision_rounding=move.product_uom.rounding),
                        'workorder_id': self.id,
                        'done_wo': False,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })
                    self.active_move_line_ids += self.move_line_id
                else:
                    self.move_line_id = lines_without_lots[0]
                # If tracked by lot, put the remaining quantity in (only) one move line
                if move.product_id.tracking == 'lot':
                    lines_without_lots[1::].unlink()
                    if self.component_remaining_qty > 0:
                        self.move_line_id.copy(default={'qty_done': self.component_remaining_qty})
                # Write the lot and qty to the move line
                self.move_line_id.write({'lot_id': self.lot_id.id, 'qty_done': float_round(self.qty_done, precision_rounding=move.product_uom.rounding)})
                # Create another quality check if necessary
                parent_id = self.current_quality_check_id
                if parent_id.parent_id:
                    parent_id = parent_id.parent_id
                subsequent_substeps = self.env['quality.check'].search([('parent_id', '=', parent_id.id), ('id', '>', self.current_quality_check_id.id)])
                if self.component_remaining_qty > 0 and not subsequent_substeps:
                    # Creating quality checks
                    quality_check_data = {
                        'workorder_id': self.id,
                        'product_id': self.product_id.id,
                        'parent_id': parent_id.id,
                        'finished_product_sequence': self.qty_produced,
                        'qty_done': self.component_remaining_qty if self.component_tracking != 'serial' else 1.0,
                    }
                    if self.current_quality_check_id.point_id:
                        quality_check_data.update({
                            'point_id': self.current_quality_check_id.point_id.id,
                            'team_id': self.current_quality_check_id.point_id.team_id.id,
                        })
                    else:
                        quality_check_data.update({
                            'component_id': self.current_quality_check_id.component_id.id,
                            'team_id': self.current_quality_check_id.team_id.id,
                        })
                    self.env['quality.check'].create(quality_check_data)
        self.current_quality_check_id.write({
            'quality_state': state,
            'user_id': self.env.user.id,
            'control_date': datetime.now()})
        old_check_id = self.current_quality_check_id
        if self.skip_completed_checks:
            self._change_quality_check(increment=1, children=1, checks=self.skipped_check_ids)
        else:
            self._change_quality_check(increment=1, children=1)
        if state == 'fail' and old_check_id.failure_message:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'quality.check',
                'views': [[self.env.ref('quality_mrp.quality_check_failure_message').id, 'form']],
                'name': _('Failure Message'),
                'target': 'new',
                'res_id': old_check_id.id,
            }

    def action_skip(self):
        self.ensure_one()
        if self.qty_producing <= 0 or self.qty_producing > self.qty_remaining:
            raise UserError(_('Please ensure the quantity to produce is nonnegative and does not exceed the remaining quantity.'))
        if self.skip_completed_checks:
            self._change_quality_check(increment=1, children=1, checks=self.skipped_check_ids)
        else:
            self._change_quality_check(increment=1, children=1)

    def action_first_skipped_step(self):
        self.ensure_one()
        self.skip_completed_checks = True
        self._change_quality_check(position=0, children=1, checks=self.skipped_check_ids)

    def action_previous(self):
        self.ensure_one()
        self._change_quality_check(increment=-1, children=1)

    # Technical function to change the current quality check.
    #
    # params:
    #     children - boolean - Whether to account for 'children' quality checks, which are generated on-the-fly
    #     position - integer - Goes to step <position>, after reordering
    #     checks - list - If provided, consider only checks in <checks>
    #     goto - integer - Goes to quality_check with id=<goto>
    #     increment - integer - Change quality check relatively to the current one, after reordering
    def _change_quality_check(self, **params):
        self.ensure_one()
        check_id = None
        # Determine the list of checks to consider
        checks = params['checks'] if 'checks' in params else self.check_ids
        if not params.get('children'):
            checks = checks.filtered(lambda c: not c.parent_id)
        # We need to make sure the current quality check is in our list
        # when we compute position relatively to the current quality check.
        if 'increment' in params or 'checks' in params and self.current_quality_check_id not in checks:
            checks |= self.current_quality_check_id
        # Restrict to checks associated with the current production
        checks = checks.filtered(lambda c: c.finished_product_sequence == self.qty_produced)
        # As some checks are generated on the fly,
        # we need to ensure that all 'children' steps are grouped together.
        # Missing steps are added at the end.
        def sort_quality_checks(check):
            # Useful tuples to compute the order
            parent_point_sequence = (check.parent_id.point_id.sequence, check.parent_id.point_id.id)
            point_sequence = (check.point_id.sequence, check.point_id.id)
            # Parent quality checks are sorted according to the sequence number of their associated quality point,
            # with chronological order being the tie-breaker.
            if check.point_id and not check.parent_id:
                score = (0, 0) + point_sequence + (0, 0)
            # Children steps follow their parents, honouring their quality point sequence number,
            # with chronological order being the tie-breaker.
            elif check.point_id:
                score = (0, 0) + parent_point_sequence + point_sequence
            # Checks without points go at the end and are ordered chronologically
            elif not check.parent_id:
                score = (check.id, 0, 0, 0, 0, 0)
            # Children without points follow their respective parents, in chronological order
            else:
                score = (check.parent_id.id, check.id, 0, 0, 0, 0)
            return score
        ordered_check_ids = checks.sorted(key=sort_quality_checks).ids
        # We manually add a final 'Summary' step
        # which is not associated with a specific quality_check (hence the 'False' id).
        ordered_check_ids.append(False)
        # Determine the quality check we are switching to
        if 'increment' in params:
            current_id = self.current_quality_check_id.id
            position = ordered_check_ids.index(current_id)
            check_id = self.current_quality_check_id.id
            if position + params['increment'] in range(0, len(ordered_check_ids)):
                position += params['increment']
                check_id = ordered_check_ids[position]
        elif params.get('position') in range(0, len(ordered_check_ids)):
            position = params['position']
            check_id = ordered_check_ids[position]
        elif params.get('goto') in ordered_check_ids:
            check_id = params['goto']
            position = ordered_check_ids.index(check_id)
        # Change the quality check and the worksheet page if necessary
        if check_id is not None:
            next_check = self.env['quality.check'].browse(check_id)
            change_worksheet_page = position != len(ordered_check_ids) - 1 and next_check.point_id.worksheet == 'scroll'
            old_allow_producing_quantity_change = self.allow_producing_quantity_change
            self.write({
                'allow_producing_quantity_change': True if params.get('position') == 0 else False,
                'current_quality_check_id': check_id,
                'is_first_step': position == 0,
                'is_last_step': check_id == False,
                'worksheet_page': next_check.point_id.worksheet_page if change_worksheet_page else self.worksheet_page,
            })
            # Update the default quantities in component registration steps
            if old_allow_producing_quantity_change and not self.allow_producing_quantity_change:
                for check in self.check_ids.filtered(lambda c: c.test_type == 'register_consumed_materials' and c.point_id and c.point_id.component_id.tracking != 'serial' and c.quality_state == 'none'):
                    moves = self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id == check.point_id.component_id)
                    check.qty_done = float_round(check.qty_done * self.qty_producing, precision_rounding=moves[0].product_uom.rounding)

    def action_menu(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'views': [[self.env.ref('quality_mrp.mrp_workorder_view_form_tablet_menu').id, 'form']],
            'name': _('Menu'),
            'target': 'new',
            'res_id': self.id,
        }

    def _compute_check(self):
        for workorder in self:
            todo = False
            fail = False
            for check in workorder.check_ids:
                if check.quality_state == 'none':
                    todo = True
                elif check.quality_state == 'fail':
                    fail = True
                if fail and todo:
                    break
            workorder.quality_check_fail = fail
            workorder.quality_check_todo = todo

    def _compute_quality_alert_count(self):
        for workorder in self:
            workorder.quality_alert_count = len(workorder.quality_alert_ids)

    def open_quality_alert_wo(self):
        self.ensure_one()
        action = self.env.ref('quality.quality_alert_action_check').read()[0]
        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_workorder_id': self.id,
            'default_production_id': self.production_id.id,
            'default_workcenter_id': self.workcenter_id.id,
            }
        action['domain'] = [('id', 'in', self.quality_alert_ids.ids)]
        action['views'] = [(False, 'tree'),(False,'form')]
        if self.quality_alert_count == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.quality_alert_ids.id
        return action

    def button_quality_alert(self):
        self.ensure_one()
        action = self.env.ref('quality.quality_alert_action_check').read()[0]
        action['target'] = 'new'
        action['views'] = [(False, 'form')]
        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_workorder_id': self.id,
            'default_production_id': self.production_id.id,
            'default_workcenter_id': self.workcenter_id.id,
        }
        return action

    def _create_checks(self):
        for wo in self:
            # Track components which have a control point
            component_list = []

            production = wo.production_id
            points = self.env['quality.point'].search([('operation_id', '=', wo.operation_id.id),
                                                       ('picking_type_id', '=', production.picking_type_id.id),
                                                       '|', ('product_id', '=', production.product_id.id),
                                                       '&', ('product_id', '=', False), ('product_tmpl_id', '=', production.product_id.product_tmpl_id.id)])
            for point in points:
                if point.check_execute_now():
                    if point.component_id:
                        component_list.append(point.component_id.id)
                    moves = wo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id == point.component_id)
                    qty_done = 1.0
                    if point.component_id and moves and point.component_id.tracking != 'serial':
                        qty_done = float_round(sum(moves.mapped('unit_factor')), precision_rounding=moves[0].product_uom.rounding)
                    self.env['quality.check'].create({'workorder_id': wo.id,
                                                  'point_id': point.id,
                                                  'team_id': point.team_id.id,
                                                  'product_id': production.product_id.id,
                                                  # Fill in the full quantity by default
                                                  'qty_done': qty_done,
                                                  # Two steps are from the same production
                                                  # if and only if the produced quantities at the time they were created are equal.
                                                  'finished_product_sequence': wo.qty_produced,
                                                 })

            # Generate quality checks associated with unreferenced components
            bom_ids = self.env['mrp.bom'].search([('product_tmpl_id', '=', production.product_id.product_tmpl_id.id)])
            bom_line_ids = bom_ids.mapped('bom_line_ids').filtered(lambda l: l.operation_id == wo.operation_id)
            # If last step, add bom lines not associated with any operation
            if not wo.next_work_order_id:
                bom_line_ids += bom_ids.mapped('bom_line_ids').filtered(lambda l: not l.operation_id)
            components = bom_line_ids.mapped('product_id').filtered(lambda product: product.tracking != 'none' and product.id not in component_list)
            quality_team_id = self.env['quality.alert.team'].search([], limit=1).id
            for component in components:
                moves = wo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id == component)
                qty_done = 1.0
                if component.tracking != 'serial':
                    qty_done = float_round(sum(moves.mapped('unit_factor')) * wo.qty_producing, precision_rounding=moves[0].product_uom.rounding)
                self.env['quality.check'].create({
                    'workorder_id': wo.id,
                    'product_id': production.product_id.id,
                    'component_id': component.id,
                    'team_id': quality_team_id,
                    # Fill in the full quantity by default
                    'qty_done': float_round(sum(moves.mapped('unit_factor')) * wo.qty_producing, precision_rounding=moves[0].product_uom.rounding) if component.tracking != 'serial' else 1.0,
                    # Two steps are from the same production
                    # if and only if the produced quantities at the time they were created are equal.
                    'finished_product_sequence': wo.qty_produced,
                })

            # Set default quality_check
            wo.skip_completed_checks = False
            wo._change_quality_check(position=0)

    def record_production(self):
        self.ensure_one()
        if any([(x.quality_state == 'none') for x in self.check_ids]):
            raise UserError(_('You still need to do the quality checks!'))
        if (self.production_id.product_id.tracking != 'none') and not self.final_lot_id:
            raise UserError(_('You should provide a lot for the final product'))
        if self.check_ids:
            # Check if you can attribute the lot to the checks
            if (self.production_id.product_id.tracking != 'none') and self.final_lot_id:
                checks_to_assign = self.check_ids.filtered(lambda x: not x.lot_id)
                if checks_to_assign:
                    checks_to_assign.write({'lot_id': self.final_lot_id.id})
        res = super(MrpProductionWorkcenterLine, self).record_production()
        if self.qty_producing > 0:
            self._create_checks()
        return res

    def check_quality(self):
        self.ensure_one()
        checks = self.check_ids.filtered(lambda x: x.quality_state == 'none')
        if checks:
            action_rec = self.env.ref('quality.quality_check_action_small')
            if action_rec:
                action = action_rec.read([])[0]
                action['context'] = dict(self.env.context, active_model='mrp.workorder')
                action['res_id'] = checks[0].id
                return action

    # --------------------------
    # Buttons from quality.check
    # --------------------------

    def open_tablet_view(self):
        self.ensure_one()
        if not self.is_user_working and self.working_state != 'blocked':
            self.button_start()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'views': [[self.env.ref('quality_mrp.mrp_workorder_view_form_tablet').id, 'form']],
            'res_id': self.id,
            'target': 'fullscreen',
            'flags': {
                'headless': True,
                'form_view_initial_mode': 'edit',
            },
        }

    def action_next(self):
        self.ensure_one();
        return self._next()

    def do_fail(self):
        self.ensure_one()
        return self._next('fail')

    def do_finish(self):
        self.record_production()
        action = self.env.ref('quality_mrp.mrp_workorder_action_tablet').read()[0]
        action['domain'] = [('state', 'not in', ['done', 'cancel', 'pending']), ('workcenter_id', '=', self.workcenter_id.id)]
        return action

    def do_pass(self):
        self.ensure_one()
        return self._next('pass')

    def do_measure(self):
        self.ensure_one()
        point_id = self.current_quality_check_id.point_id
        if self.measure < point_id.tolerance_min or self.measure > point_id.tolerance_max:
            return self.do_fail()
        else:
            return self.do_pass()
