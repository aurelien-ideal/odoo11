# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = "sale.order"

    subscription_management = fields.Selection(string='Subscription Management', selection=[('create', 'Creation'), ('renew', 'Renewal'), ('upsell', 'Upselling')],
                                               default='create',
                                               help="Creation: The Sales Order created the subscription\n"
                                                    "Upselling: The Sales Order added lines to the subscription\n"
                                                    "Renewal: The Sales Order replaced the subscription's content with its own")
    subscription_count = fields.Integer(compute='_compute_subscription_count')

    def _compute_subscription_count(self):
        """Compute the number of distinct subscriptions linked to the order."""
        order_line_data = self.env['sale.order.line'].read_group([('subscription_id', '!=', False), ('order_id', 'in', self.ids)], ['subscription_id', 'order_id'], ['subscription_id', 'order_id'])
        subscription_count = len([data['subscription_id'][0] for data in order_line_data])
        for order in self:
            order.subscription_count = subscription_count

    def action_open_subscriptions(self):
        """Display the linked subscription and adapt the view to the number of records to display."""
        self.ensure_one()
        subscriptions = self.order_line.mapped('subscription_id')
        action = self.env.ref('sale_subscription.sale_subscription_action').read()[0]
        if len(subscriptions) > 1:
            action['domain'] = [('id', 'in', subscriptions.ids)]
        elif len(subscriptions) == 1:
            action['views'] = [(self.env.ref('sale_subscription.sale_subscription_view_form').id, 'form')]
            action['res_id'] = subscriptions.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _prepare_subscription_data(self, template):
        """Prepare a dictionnary of values to create a subscription from a template."""
        self.ensure_one()
        values = {
            'name': template.name,
            'state': 'open',
            'template_id': template.id,
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'date_start': fields.Date.today(),
            'description': self.note or template.description,
            'pricelist_id': self.pricelist_id.id,
            'company_id': self.company_id.id,
            'analytic_account_id': self.analytic_account_id.id,
            'payment_token_id': self.payment_tx_id.payment_token_id.id if template.payment_mandatory else False
        }
        # compute the next date
        today = datetime.date.today()
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        invoicing_period = relativedelta(**{periods[template.recurring_rule_type]: template.recurring_interval})
        recurring_next_date = today + invoicing_period
        values['recurring_next_date'] = fields.Date.to_string(recurring_next_date)
        return values

    def update_existing_subscriptions(self):
        """
        Update subscriptions already linked to the order by updating or creating lines.

        :rtype: list(integer)
        :return: ids of modified subscriptions
        """
        res = []
        for order in self:
            subscriptions = order.order_line.mapped('subscription_id')
            if subscriptions and order.subscription_management != 'renew':
                order.subscription_management = 'upsell'
            res.append(subscriptions.ids)
            if order.subscription_management == 'renew':
                subscriptions.wipe()
                subscriptions.increment_period()
            for subscription in subscriptions:
                subscription_lines = order.order_line.filtered(lambda l: l.subscription_id == subscription)
                line_values = subscription_lines._update_subscription_line_data(subscription)
                subscription.write({'recurring_invoice_line_ids': line_values})
        return res

    def create_subscriptions(self):
        """
        Create subscriptions based on the products' subscription template.

        Create subscriptions based on the templates found on order lines' products. Note that only
        lines not already linked to a subscription are processed; one subscription is created per
        distinct subscription template found.

        :rtype: list(integer)
        :return: ids of newly create subscriptions
        """
        res = []
        for order in self:
            to_create = self._split_subscription_lines()
            # create a subscription for each template with all the necessary lines
            for template in to_create:
                values = self._prepare_subscription_data(template)
                values['recurring_invoice_line_ids'] = to_create[template]._prepare_subscription_line_data()
                subscription = self.env['sale.subscription'].sudo().create(values)
                res.append(subscription.id)
                to_create[template].write({'subscription_id': subscription.id})
                subscription.message_post_with_view(
                    'mail.message_origin_link', values={'self': subscription, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id, author_id=self.env.user.partner_id.id
                )
        return res

    def _split_subscription_lines(self):
        """Split the order line according to subscription templates that must be created."""
        self.ensure_one()
        res = dict()
        new_sub_lines = self.order_line.filtered(lambda l: not l.subscription_id and l.product_id.subscription_template_id)
        templates = new_sub_lines.mapped('product_id').mapped('subscription_template_id')
        for template in templates:
            lines = self.order_line.filtered(lambda l: l.product_id.subscription_template_id == template)
            res[template] = lines
        return res

    @api.multi
    def action_confirm(self):
        """Update and/or create subscriptions on order confirmation."""
        res = super(SaleOrder, self).action_confirm()
        self.update_existing_subscriptions()
        self.create_subscriptions()
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    subscription_id = fields.Many2one('sale.subscription', 'Subscription', copy=False)

    def _prepare_invoice_line(self, qty):
        """
        Override to add subscription-specific behaviours.

        Display the invoicing period in the invoice line description, link the invoice line to the
        correct subscription and to the subscription's analytic account if present.
        """
        res = super(SaleOrderLine, self)._prepare_invoice_line(qty)
        if self.subscription_id and self.order_id.subscription_management != 'upsell':
            next_date = fields.Date.from_string(self.subscription_id.recurring_next_date)
            periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
            previous_date = next_date - relativedelta(**{periods[self.subscription_id.recurring_rule_type]: self.subscription_id.recurring_interval})
            format_date = self.env['ir.qweb.field.date'].value_to_html
            period_msg = _("Invoicing period: %s - %s") % (format_date(fields.Date.to_string(previous_date), {}), format_date(fields.Date.to_string(next_date - relativedelta(days=1)), {}))
            res.update({
                'subscription_id': self.subscription_id.id,
                'name': res['name'] + '\n' + period_msg})
            if self.subscription_id.analytic_account_id:
                res['account_analytic_id'] = self.subscription_id.analytic_account_id.id
        return res

    def _prepare_subscription_line_data(self):
        """Prepare a dictionnary of values to add lines to a subscription."""
        values = list()
        for line in self:
            values.append((0, False, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.product_uom_qty,
                'uom_id': line.product_uom.id,
                'price_unit': line.price_unit,
                'discount': line.discount if line.order_id.subscription_management != 'upsell' else False,
            }))
        return values

    def _update_subscription_line_data(self, subscription):
        """Prepare a dictionnary of values to add or update lines on a subscription."""
        values = list()
        for line in self:
            sub_line = subscription.recurring_invoice_line_ids.filtered(lambda l: (l.product_id, l.uom_id) == (line.product_id, line.product_uom))
            if sub_line:
                values.append((1, sub_line.id, {
                    'quantity': sub_line.quantity + line.product_uom_qty,
                }))
            else:
                values.append(line._prepare_subscription_line_data()[0])
        return values
