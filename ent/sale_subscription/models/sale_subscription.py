# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import datetime
import uuid
import time
import traceback

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import format_date

from odoo.addons import decimal_precision as dp

_logger = logging.getLogger(__name__)


class SaleSubscription(models.Model):
    _name = "sale.subscription"
    _description = "Sale Subscription"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, track_visibility="always")
    code = fields.Char(string="Reference", required=True, track_visibility="onchange", index=True)
    state = fields.Selection([('draft', 'New'), ('open', 'In Progress'), ('pending', 'To Renew'),
                              ('close', 'Closed'), ('cancel', 'Cancelled')],
                             string='Status', required=True, track_visibility='onchange', copy=False, default='draft')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    company_id = fields.Many2one('res.company', string="Company", default=lambda s: s.env['res.company']._company_default_get(), required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    tag_ids = fields.Many2many('account.analytic.tag', string='Tags')
    date_start = fields.Date(string='Start Date', default=fields.Date.today)
    date = fields.Date(string='End Date', track_visibility='onchange', help="If set in advance, the subscription will be set to pending 1 month before the date and will be closed on the date set in this field.")
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True)
    currency_id = fields.Many2one('res.currency', related='pricelist_id.currency_id', string='Currency', readonly=True)
    recurring_invoice_line_ids = fields.One2many('sale.subscription.line', 'analytic_account_id', string='Invoice Lines', copy=True)
    recurring_rule_type = fields.Selection(string='Recurrence', help="Invoice automatically repeat at specified interval", related="template_id.recurring_rule_type", readonly=1)
    recurring_interval = fields.Integer(string='Repeat Every', help="Repeat every (Days/Week/Month/Year)", related="template_id.recurring_interval", readonly=1)
    recurring_next_date = fields.Date(string='Date of Next Invoice', default=fields.Date.today, help="The next invoice will be created on this date then the period will be extended.")
    recurring_total = fields.Float(compute='_compute_recurring_total', string="Recurring Price", store=True, track_visibility='onchange')
    recurring_monthly = fields.Float(compute='_compute_recurring_monthly', string="Monthly Recurring Revenue", store=True)
    close_reason_id = fields.Many2one("sale.subscription.close.reason", string="Close Reason", track_visibility='onchange')
    template_id = fields.Many2one('sale.subscription.template', string='Subscription Template', required=True, track_visibility='onchange')
    payment_mandatory = fields.Boolean(related='template_id.payment_mandatory')
    description = fields.Text()
    user_id = fields.Many2one('res.users', string='Salesperson', track_visibility='onchange')
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    country_id = fields.Many2one('res.country', related='analytic_account_id.partner_id.country_id', store=True)
    industry_id = fields.Many2one('res.partner.industry', related='analytic_account_id.partner_id.industry_id', store=True)
    sale_order_count = fields.Integer(compute='_compute_sale_order_count')
    # customer portal
    uuid = fields.Char('Account UUID', default=lambda s: uuid.uuid4(), copy=False, required=True)
    website_url = fields.Char('Website URL', compute='_website_url', help='The full URL to access the document through the website.')
    payment_token_id = fields.Many2one('payment.token', 'Payment Token', help='If not set, the default payment token of the partner will be used.', domain="[('partner_id','=',partner_id)]", oldname='payment_method_id')
    # add tax calculation
    recurring_amount_tax = fields.Float('Taxes', compute="_amount_all")
    recurring_amount_total = fields.Float('Total', compute="_amount_all")

    _sql_constraints = [
        ('uuid_uniq', 'unique (uuid)', """UUIDs (Universally Unique IDentifier) for Sale Subscriptions should be unique!"""),
    ]

    def _compute_sale_order_count(self):
        raw_data = self.env['sale.order.line'].read_group(
            [('subscription_id', '!=', False)],
            ['subscription_id', 'order_id'],
            ['subscription_id', 'order_id']
        )

        order_count = len([sub for sub in raw_data if sub["subscription_id"][0] in self.ids])
        for subscription in self:
            subscription.sale_order_count = order_count

    def action_open_sales(self):
        self.ensure_one()
        sales = self.env['sale.order'].search([('order_line.subscription_id', 'in', self.ids)])
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[self.env.ref('sale_subscription.sale_order_view_tree_subscription').id, "tree"],
                      [self.env.ref('sale.view_order_form').id, "form"],
                      [False, "kanban"], [False, "calendar"], [False, "pivot"], [False, "graph"]],
            "domain": [["id", "in", sales.ids]],
            "context": {"create": False},
            "name": _("Sales Orders"),
        }

    def partial_invoice_line(self, sale_order, option_line, refund=False, date_from=False):
        """ Add an invoice line on the sales order for the specified option and add a discount
        to take the partial recurring period into account """
        order_line_obj = self.env['sale.order.line']
        values = {
            'order_id': sale_order.id,
            'product_id': option_line.product_id.id,
            'subscription_id': self.id,
            'product_uom_qty': option_line.quantity,
            'product_uom': option_line.uom_id.id,
            'discount': (1 - self.partial_recurring_invoice_ratio(date_from=date_from)) * 100,
            'price_unit': self.pricelist_id.with_context({'uom': option_line.uom_id.id}).get_product_price(option_line.product_id, 1, False),
            'name': option_line.name,
        }
        return order_line_obj.create(values)

    def partial_recurring_invoice_ratio(self, date_from=False):
        """Computes the ratio of the amount of time remaining in the current invoicing period
        over the total length of said invoicing period"""
        if date_from:
            date = fields.Date.from_string(date_from)
        else:
            date = datetime.date.today()
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        if fields.Date.from_string(self.recurring_next_date) == date:
           return 0
        invoicing_period = relativedelta(**{periods[self.recurring_rule_type]: self.recurring_interval})
        recurring_next_invoice = fields.Date.from_string(self.recurring_next_date)
        recurring_last_invoice = recurring_next_invoice - invoicing_period
        time_to_invoice = recurring_next_invoice - date - datetime.timedelta(days=1)
        ratio = float(time_to_invoice.days) / float((recurring_next_invoice - recurring_last_invoice).days)
        return ratio

    @api.model
    def default_get(self, fields):
        defaults = super(SaleSubscription, self).default_get(fields)
        if 'code' in fields:
            defaults.update(code=self.env['ir.sequence'].next_by_code('sale.subscription') or 'New')
        return defaults

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values:
            return 'sale_subscription.subtype_state_change'
        return super(SaleSubscription, self)._track_subtype(init_values)

    def _compute_invoice_count(self):
        Invoice = self.env['account.invoice']
        for subscription in self:
            subscription.invoice_count = Invoice.search_count([('invoice_line_ids.subscription_id', '=', subscription.id)])

    @api.depends('recurring_invoice_line_ids', 'recurring_invoice_line_ids.quantity', 'recurring_invoice_line_ids.price_subtotal')
    def _compute_recurring_total(self):
        for account in self:
            account.recurring_total = sum(line.price_subtotal for line in account.recurring_invoice_line_ids)

    @api.depends('recurring_total', 'template_id.recurring_interval', 'template_id.recurring_rule_type')
    def _compute_recurring_monthly(self):
        # Generally accepted ratios for monthly reporting
        interval_factor = {
            'daily': 30.0,
            'weekly': 30.0 / 7.0,
            'monthly': 1.0,
            'yearly': 1.0 / 12.0,
        }
        for sub in self:
            sub.recurring_monthly = (
                sub.recurring_total * interval_factor[sub.recurring_rule_type] / sub.recurring_interval
            ) if sub.template_id else 0

    @api.depends('uuid')
    def _website_url(self):
        for account in self:
            account.website_url = '/my/subscription/%s/%s' % (account.id, account.uuid)

    @api.depends('recurring_invoice_line_ids', 'recurring_total')
    def _amount_all(self):
        for account in self:
            account_sudo = account.sudo()
            val = val1 = 0.0
            cur = account_sudo.pricelist_id.currency_id
            for line in account_sudo.recurring_invoice_line_ids:
                val1 += line.price_subtotal
                val += line._amount_line_tax()
            account.recurring_amount_tax = cur.round(val)
            account.recurring_amount_total = account.recurring_amount_tax + account.recurring_total

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        self.pricelist_id = self.partner_id.property_product_pricelist.id
        if self.partner_id.user_id:
            self.user_id = self.partner_id.user_id

    @api.onchange('template_id')
    def on_change_template(self):
        if self.template_id:
            # Check if record is a new record or exists in db by checking its _origin
            # note that this property is not always set, hence the getattr
            if not getattr(self, '_origin', self.browse()) and not isinstance(self.id, int):
                self.description = self.template_id.description

    @api.model
    def create(self, vals):
        vals['code'] = vals.get('code') or self.env.context.get('default_code') or self.env['ir.sequence'].next_by_code('sale.subscription') or 'New'
        if vals.get('name', 'New') == 'New':
            vals['name'] = vals['code']
        subscription = super(SaleSubscription, self).create(vals)
        if subscription.partner_id:
            subscription.message_subscribe(subscription.partner_id.ids)
        return subscription

    def write(self, vals):
        if vals.get('partner_id'):
            self.message_subscribe([vals['partner_id']])
        return super(SaleSubscription, self).write(vals)

    @api.model_cr_context
    def _init_column(self, column_name):
        # to avoid generating a single default uuid when installing the module,
        # we need to set the default row by row for this column
        if column_name == "uuid":
            _logger.debug("Table '%s': setting default value of new column %s to unique values for each row",
                          self._table, column_name)
            self.env.cr.execute("SELECT id FROM %s WHERE uuid IS NULL" % self._table)
            acc_ids = self.env.cr.dictfetchall()
            query_list = [{'id': acc_id['id'], 'uuid': str(uuid.uuid4())} for acc_id in acc_ids]
            query = 'UPDATE ' + self._table + ' SET uuid = %(uuid)s WHERE id = %(id)s;'
            self.env.cr._obj.executemany(query, query_list)
            self.env.cr.commit()

        else:
            super(SaleSubscription, self)._init_column(column_name)

    def name_get(self):
        res = []
        for sub in self:
            name = '%s - %s' % (sub.code, sub.partner_id.name) if sub.code else sub.partner_id.name
            res.append((sub.id, '%s/%s' % (sub.template_id.code, name) if sub.template_id.code else name))
        return res

    def action_subscription_invoice(self):
        self.ensure_one()
        invoices = self.env['account.invoice'].search([('invoice_line_ids.subscription_id', 'in', self.ids)])
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        action["context"] = {"create": False}
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.model
    def cron_account_analytic_account(self):
        today = fields.Date.today()
        next_month = fields.Date.to_string(fields.Date.from_string(today) + relativedelta(months=1))

        # set to pending if date is in less than a month
        domain_pending = [('date', '<', next_month), ('state', '=', 'open')]
        subscriptions_pending = self.search(domain_pending)
        subscriptions_pending.write({'state': 'pending'})

        # set to close if data is passed
        domain_close = [('date', '<', today), ('state', 'in', ['pending', 'open'])]
        subscriptions_close = self.search(domain_close)
        subscriptions_close.write({'state': 'close'})

        return dict(pending=subscriptions_pending.ids, closed=subscriptions_close.ids)

    @api.model
    def _cron_recurring_create_invoice(self):
        return self._recurring_create_invoice(automatic=True)

    def set_open(self):
        return self.write({'state': 'open', 'date': False})

    def set_pending(self):
        return self.write({'state': 'pending'})

    def set_cancel(self):
        return self.write({'state': 'cancel'})

    def set_close(self):
        return self.write({'state': 'close', 'date': fields.Date.from_string(fields.Date.today())})

    def _prepare_invoice_data(self):
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_("You must first select a Customer for Subscription %s!") % self.name)

        if 'force_company' in self.env.context:
            company = self.env['res.company'].browse(self.env.context['force_company'])
        else:
            company = self.company_id
            self = self.with_context(force_company=company.id, company_id=company.id)

        fpos_id = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id)
        journal = self.template_id.journal_id or self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError(_('Please define a sale journal for the company "%s".') % (company.name or '', ))

        next_date = fields.Date.from_string(self.recurring_next_date)
        if not next_date:
            raise UserError(_('Please define Date of Next Invoice of "%s".') % (self.display_name,))
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        end_date = next_date + relativedelta(**{periods[self.recurring_rule_type]: self.recurring_interval})
        end_date = end_date - relativedelta(days=1)     # remove 1 day as normal people thinks in term of inclusive ranges.
        addr = self.partner_id.address_get(['delivery'])

        return {
            'account_id': self.partner_id.property_account_receivable_id.id,
            'type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'partner_shipping_id': addr['delivery'],
            'currency_id': self.pricelist_id.currency_id.id,
            'journal_id': journal.id,
            'origin': self.code,
            'fiscal_position_id': fpos_id,
            'payment_term_id': self.partner_id.property_payment_term_id.id,
            'company_id': company.id,
            'comment': _("This invoice covers the following period: %s - %s") % (format_date(self.env, next_date), format_date(self.env, end_date)),
            'user_id': self.user_id.id,
        }

    def _prepare_invoice_line(self, line, fiscal_position):
        if 'force_company' in self.env.context:
            company = self.env['res.company'].browse(self.env.context['force_company'])
        else:
            company = line.analytic_account_id.company_id
            line = line.with_context(force_company=company.id, company_id=company.id)

        account = line.product_id.property_account_income_id
        if not account:
            account = line.product_id.categ_id.property_account_income_categ_id
        account_id = fiscal_position.map_account(account).id

        tax = line.product_id.taxes_id.filtered(lambda r: r.company_id == company)
        tax = fiscal_position.map_tax(tax)
        return {
            'name': line.name,
            'account_id': account_id,
            'account_analytic_id': line.analytic_account_id.analytic_account_id.id,
            'subscription_id': line.analytic_account_id.id,
            'price_unit': line.price_unit or 0.0,
            'discount': line.discount,
            'quantity': line.quantity,
            'uom_id': line.uom_id.id,
            'product_id': line.product_id.id,
            'invoice_line_tax_ids': [(6, 0, tax.ids)],
            'analytic_tag_ids': [(6, 0, line.analytic_account_id.tag_ids.ids)]
        }

    def _prepare_invoice_lines(self, fiscal_position):
        self.ensure_one()
        fiscal_position = self.env['account.fiscal.position'].browse(fiscal_position)
        return [(0, 0, self._prepare_invoice_line(line, fiscal_position)) for line in self.recurring_invoice_line_ids]

    def _prepare_invoice(self):
        invoice = self._prepare_invoice_data()
        invoice['invoice_line_ids'] = self._prepare_invoice_lines(invoice['fiscal_position_id'])
        return invoice

    def recurring_invoice(self):
        self._recurring_create_invoice()
        return self.action_subscription_invoice()

    def _prepare_renewal_order_values(self):
        res = dict()
        for subscription in self:
            order_lines = []
            fpos_id = self.env['account.fiscal.position'].get_fiscal_position(subscription.partner_id.id)
            for line in subscription.recurring_invoice_line_ids:
                order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.product_tmpl_id.name,
                    'subscription_id': subscription.id,
                    'product_uom': line.uom_id.id,
                    'product_uom_qty': line.quantity,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                }))
            addr = subscription.partner_id.address_get(['delivery', 'invoice'])
            res[subscription.id] = {
                'pricelist_id': subscription.pricelist_id.id,
                'partner_id': subscription.partner_id.id,
                'partner_invoice_id': addr['invoice'],
                'partner_shipping_id': addr['delivery'],
                'currency_id': subscription.pricelist_id.currency_id.id,
                'order_line': order_lines,
                'analytic_account_id': subscription.analytic_account_id.id,
                'subscription_management': 'renew',
                'note': subscription.description,
                'fiscal_position_id': fpos_id,
                'user_id': subscription.user_id.id,
                'payment_term_id': subscription.partner_id.property_payment_term_id.id,
            }
        return res

    def prepare_renewal_order(self):
        self.ensure_one()
        values = self._prepare_renewal_order_values()
        order = self.env['sale.order'].create(values[self.id])
        order.order_line._compute_tax_id()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": order.id,
        }

    def increment_period(self):
        for subscription in self:
            current_date = subscription.recurring_next_date or self.default_get(['recurring_next_date'])['recurring_next_date']
            periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
            new_date = fields.Date.from_string(current_date) + relativedelta(**{periods[subscription.recurring_rule_type]: subscription.recurring_interval})
            subscription.write({'recurring_next_date': new_date})

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = ['|', ('code', operator, name), ('name', operator, name)]
        partners = self.env['res.partner'].search([('name', operator, name)], limit=limit)
        if partners:
            domain = ['|'] + domain + [('partner_id', 'in', partners.ids)]
        rec = self.search(domain + args, limit=limit)
        return rec.name_get()

    def wipe(self):
        """Wipe a subscription clean by deleting all its lines."""
        lines = self.mapped('recurring_invoice_line_ids')
        lines.unlink()
        return True

    @api.multi
    def open_website_url(self):
        return {
            'type': 'ir.actions.act_url',
            'url': self.website_url,
            'target': 'self',
        }

    def add_option(self, option_id):
        pass

    def set_option(self, subscription, new_option, price):
        pass

    def remove_option(self, option_id):
        pass

    def _compute_options(self):
        pass

    # online payments
    @api.one
    def _do_payment(self, payment_token, invoice, two_steps_sec=True):
        tx_obj = self.env['payment.transaction']
        reference = "SUB%s-%s" % (self.id, datetime.datetime.now().strftime('%y%m%d_%H%M%S'))
        values = {
            'amount': invoice.amount_total,
            'acquirer_id': payment_token.acquirer_id.id,
            'type': 'server2server',
            'currency_id': invoice.currency_id.id,
            'reference': reference,
            'payment_token_id': payment_token.id,
            'partner_id': self.partner_id.id,
            'partner_country_id': self.partner_id.country_id.id,
            'invoice_id': invoice.id,
            'callback_model_id': self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1).id,
            'callback_res_id': self.id,
            'callback_method': 'reconcile_pending_transaction',
        }

        tx = tx_obj.create(values)

        baseurl = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        payment_secure = {'3d_secure': two_steps_sec,
                          'accept_url': baseurl + '/my/subscription/%s/payment/%s/accept/' % (self.uuid, tx.id),
                          'decline_url': baseurl + '/my/subscription/%s/payment/%s/decline/' % (self.uuid, tx.id),
                          'exception_url': baseurl + '/my/subscription/%s/payment/%s/exception/' % (self.uuid, tx.id),
                          }
        tx.s2s_do_transaction(**payment_secure)
        return tx

    @api.multi
    def reconcile_pending_transaction(self, tx, invoice=False):
        self.ensure_one()
        if not invoice:
            invoice = tx.invoice_id
        if tx.state in ['done', 'authorized']:
            invoice.write({'reference': tx.reference, 'name': tx.reference})
            if tx.acquirer_id.journal_id and tx.state == 'done':
                invoice.action_invoice_open()
                journal = tx.acquirer_id.journal_id
                invoice.with_context(default_ref=tx.reference, default_currency_id=tx.currency_id.id).pay_and_reconcile(journal, pay_amount=tx.amount)
            self.increment_period()
            self.write({'state': 'open', 'date': False})
        else:
            invoice.action_cancel()
            invoice.unlink()

    @api.multi
    def _recurring_create_invoice(self, automatic=False):
        cr = self.env.cr
        invoices = self.env['account.invoice']
        current_date = time.strftime('%Y-%m-%d')
        imd_res = self.env['ir.model.data']
        template_res = self.env['mail.template']
        if len(self) > 0:
            subscriptions = self
        else:
            domain = [('recurring_next_date', '<=', current_date),
                      ('state', 'in', ['open', 'pending'])]
            subscriptions = self.search(domain)
        if subscriptions:
            sub_data = subscriptions.read(fields=['id', 'company_id'])
            for company_id in set(data['company_id'][0] for data in sub_data):
                sub_ids = [s['id'] for s in sub_data if s['company_id'][0] == company_id]
                subs = self.with_context(company_id=company_id, force_company=company_id).browse(sub_ids)
                context_company = dict(self.env.context, company_id=company_id, force_company=company_id)
                for subscription in subs:
                    if automatic:
                        cr.commit()
                    # payment + invoice (only by cron)
                    if subscription.template_id.payment_mandatory and subscription.recurring_total and automatic:
                        try:
                            payment_token = subscription.payment_token_id
                            if payment_token:
                                invoice_values = subscription.with_context(lang=subscription.partner_id.lang)._prepare_invoice()
                                new_invoice = self.env['account.invoice'].with_context(context_company).create(invoice_values)
                                new_invoice.message_post_with_view('mail.message_origin_link',
                                    values = {'self': new_invoice, 'origin': subscription},
                                    subtype_id = self.env.ref('mail.mt_note').id)
                                new_invoice.with_context(context_company).compute_taxes()
                                tx = subscription._do_payment(payment_token, new_invoice, two_steps_sec=False)[0]
                                # commit change as soon as we try the payment so we have a trace somewhere
                                cr.commit()
                                if tx.state in ['done', 'authorized']:
                                    subscription.send_success_mail(tx, new_invoice)
                                    msg_body = 'Automatic payment succeeded. Payment reference: <a href=# data-oe-model=payment.transaction data-oe-id=%d>%s</a>; Amount: %s. Invoice <a href=# data-oe-model=account.invoice data-oe-id=%d>View Invoice</a>.' % (tx.id, tx.reference, tx.amount, new_invoice.id)
                                    subscription.message_post(body=msg_body)
                                    cr.commit()
                                else:
                                    cr.rollback()
                                    new_invoice.unlink()
                                    amount = subscription.recurring_total
                                    date_close = datetime.datetime.strptime(subscription.recurring_next_date, "%Y-%m-%d") + relativedelta(days=15)
                                    close_subscription = current_date >= date_close.strftime('%Y-%m-%d')
                                    email_context = self.env.context.copy()
                                    email_context.update({
                                        'payment_token': subscription.payment_token_id and subscription.payment_token_id.name,
                                        'renewed': False,
                                        'total_amount': amount,
                                        'email_to': subscription.partner_id.email,
                                        'code': subscription.code,
                                        'currency': subscription.pricelist_id.currency_id.name,
                                        'date_end': subscription.date,
                                        'date_close': date_close.date()
                                    })
                                    _logger.error('Fail to create recurring invoice for subscription %s', subscription.code)
                                    if close_subscription:
                                        _, template_id = imd_res.get_object_reference('sale_subscription', 'email_payment_close')
                                        template = template_res.browse(template_id)
                                        template.with_context(email_context).send_mail(subscription.id)
                                        _logger.debug("Sending Subscription Closure Mail to %s for subscription %s and closing subscription", subscription.partner_id.email, subscription.id)
                                        msg_body = 'Automatic payment failed after multiple attempts. Subscription closed automatically.'
                                        subscription.message_post(body=msg_body)
                                    else:
                                        _, template_id = imd_res.get_object_reference('sale_subscription', 'email_payment_reminder')
                                        msg_body = 'Automatic payment failed. Subscription set to "To Renew".'
                                        if (datetime.datetime.today() - datetime.datetime.strptime(subscription.recurring_next_date, '%Y-%m-%d')).days in [0, 3, 7, 14]:
                                            template = template_res.browse(template_id)
                                            template.with_context(email_context).send_mail(subscription.id)
                                            _logger.debug("Sending Payment Failure Mail to %s for subscription %s and setting subscription to pending", subscription.partner_id.email, subscription.id)
                                            msg_body += ' E-mail sent to customer.'
                                        subscription.message_post(body=msg_body)
                                    subscription.write({'state': 'close' if close_subscription else 'pending'})
                                    cr.commit()
                        except Exception:
                            cr.rollback()
                            # we assume that the payment is run only once a day
                            last_tx = self.env['payment.transaction'].search([('reference', 'like', 'SUBSCRIPTION-%s-%s' % (subscription.id, datetime.date.today().strftime('%y%m%d')))], limit=1)
                            error_message = "Error during renewal of subscription %s (%s)" % (subscription.code, 'Payment recorded: %s' % last_tx.reference if last_tx and last_tx.state == 'done' else 'No payment recorded.')
                            traceback_message = traceback.format_exc()
                            _logger.error(error_message)
                            _logger.error(traceback_message)

                    # invoice only
                    else:
                        try:
                            invoice_values = subscription.with_context(lang=subscription.partner_id.lang)._prepare_invoice()
                            new_invoice = self.env['account.invoice'].with_context(context_company).create(invoice_values)
                            new_invoice.message_post_with_view('mail.message_origin_link',
                                values = {'self': new_invoice, 'origin': subscription},
                                subtype_id = self.env.ref('mail.mt_note').id)
                            new_invoice.with_context(context_company).compute_taxes()
                            invoices += new_invoice
                            next_date = datetime.datetime.strptime(subscription.recurring_next_date or current_date, "%Y-%m-%d")
                            periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
                            invoicing_period = relativedelta(**{periods[subscription.recurring_rule_type]: subscription.recurring_interval})
                            new_date = next_date + invoicing_period
                            subscription.write({'recurring_next_date': new_date.strftime('%Y-%m-%d')})
                            if automatic:
                                cr.commit()
                        except Exception:
                            if automatic:
                                cr.rollback()
                                _logger.exception('Fail to create recurring invoice for subscription %s', subscription.code)
                            else:
                                raise
        return invoices

    def send_success_mail(self, tx, invoice):
        imd_res = self.env['ir.model.data']
        template_res = self.env['mail.template']
        current_date = time.strftime('%Y-%m-%d')
        next_date = datetime.datetime.strptime(self.recurring_next_date or current_date, "%Y-%m-%d")
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        invoicing_period = relativedelta(**{periods[self.recurring_rule_type]: self.recurring_interval})
        new_date = next_date + invoicing_period
        _, template_id = imd_res.get_object_reference('sale_subscription', 'email_payment_success')
        email_context = self.env.context.copy()
        email_context.update({
            'payment_token': self.payment_token_id.name,
            'renewed': True,
            'total_amount': tx.amount,
            'next_date': new_date.date(),
            'previous_date': self.recurring_next_date,
            'email_to': self.partner_id.email,
            'code': self.code,
            'currency': self.pricelist_id.currency_id.name,
            'date_end': self.date,
        })
        _logger.debug("Sending Payment Confirmation Mail to %s for subscription %s", self.partner_id.email, self.id)
        template = template_res.browse(template_id)
        return template.with_context(email_context).send_mail(invoice.id)


class SaleSubscriptionLine(models.Model):
    _name = "sale.subscription.line"
    _description = "Subscription Line"

    product_id = fields.Many2one('product.product', string='Product', domain="[('recurring_invoice','=',True)]", required=True)
    analytic_account_id = fields.Many2one('sale.subscription', string='Subscription')
    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(string='Quantity', help="Quantity that will be invoiced.", default=1.0)
    uom_id = fields.Many2one('product.uom', string='Unit of Measure', required=True)
    price_unit = fields.Float(string='Unit Price', required=True, digits=dp.get_precision('Product Price'))
    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'))
    price_subtotal = fields.Float(compute='_compute_price_subtotal', string='Sub Total', digits=dp.get_precision('Account'))

    @api.depends('price_unit', 'quantity', 'discount', 'analytic_account_id.pricelist_id')
    def _compute_price_subtotal(self):
        for line in self:
            line_sudo = line.sudo()
            price = line.env['account.tax']._fix_tax_included_price(line.price_unit, line_sudo.product_id.taxes_id, [])
            line.price_subtotal = line.quantity * price * (100.0 - line.discount) / 100.0
            if line.analytic_account_id.pricelist_id:
                line.price_subtotal = line_sudo.analytic_account_id.pricelist_id.currency_id.round(line.price_subtotal)

    @api.onchange('product_id', 'quantity')
    def onchange_product_id(self):
        domain = {}
        subscription = self.analytic_account_id
        company_id = subscription.company_id.id
        pricelist_id = subscription.pricelist_id.id
        context = dict(self.env.context, company_id=company_id, force_company=company_id, pricelist=pricelist_id, quantity=self.quantity)
        if not self.product_id:
            self.price_unit = 0.0
            domain['uom_id'] = []
        else:
            partner = subscription.partner_id.with_context(context)
            if partner.lang:
                context.update({'lang': partner.lang})

            product = self.product_id.with_context(context)
            self.price_unit = product.price

            name = product.display_name
            if product.description_sale:
                name += '\n' + product.description_sale
            self.name = name

            if not self.uom_id:
                self.uom_id = product.uom_id.id
            if self.uom_id.id != product.uom_id.id:
                self.price_unit = product.uom_id._compute_price(self.price_unit, self.uom_id)
            domain['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]

        return {'domain': domain}

    @api.onchange('uom_id')
    def onchange_uom_id(self):
        if not self.uom_id:
            self.price_unit = 0.0
        else:
            self.onchange_product_id()

    def get_template_option_line(self):
        """ Return the account.analytic.invoice.line.option which has the same product_id as
        the invoice line"""
        if not self.analytic_account_id and not self.analytic_account_id.template_id:
            return False
        template = self.analytic_account_id.template_id
        return template.sudo().subscription_template_option_ids.filtered(lambda r: r.product_id == self.product_id)

    def _amount_line_tax(self):
        self.ensure_one()
        val = 0.0
        product = self.product_id
        product_tmp = product.sudo().product_tmpl_id
        for tax in product_tmp.taxes_id.filtered(lambda t: t.company_id == self.analytic_account_id.company_id):
            fpos_obj = self.env['account.fiscal.position']
            partner = self.analytic_account_id.partner_id
            fpos_id = fpos_obj.with_context(force_company=self.analytic_account_id.company_id.id).get_fiscal_position(partner.id)
            fpos = fpos_obj.browse(fpos_id)
            if fpos:
                tax = fpos.map_tax(tax, product, partner)
            compute_vals = tax.compute_all(self.price_unit * (1 - (self.discount or 0.0) / 100.0), self.analytic_account_id.currency_id, self.quantity, product, partner)['taxes']
            if compute_vals:
                val += compute_vals[0].get('amount', 0)
        return val


class SaleSubscriptionCloseReason(models.Model):
    _name = "sale.subscription.close.reason"
    _order = "sequence, id"
    _description = "Subscription Close Reason"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)


class SaleSubscriptionTemplate(models.Model):
    _name = "sale.subscription.template"
    _description = "Sale Subscription Template"
    _inherit = "mail.thread"

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    code = fields.Char()
    description = fields.Text(translate=True, string="Terms and Conditions")
    recurring_rule_type = fields.Selection([('daily', 'Day(s)'), ('weekly', 'Week(s)'),
                                            ('monthly', 'Month(s)'), ('yearly', 'Year(s)'), ],
                                           string='Recurrence',
                                           help="Invoice automatically repeat at specified interval",
                                           default='monthly', track_visibility='onchange')
    recurring_interval = fields.Integer(string="Repeat Every", help="Repeat every (Days/Week/Month/Year)", default=1, track_visibility='onchange')
    user_closable = fields.Boolean(string="Closable by customer", help="If checked, the user will be able to close his account from the frontend")
    payment_mandatory = fields.Boolean('Automatic Payment', help='If set, payments will be made automatically and invoices will not be generated if payment attempts are unsuccessful.')
    product_ids = fields.One2many('product.template', 'subscription_template_id', copy=True)
    journal_id = fields.Many2one('account.journal', string="Accounting Journal", domain="[('type', '=', 'sale')]", company_dependent=True,
                                 help="If set, subscriptions with this template will invoice in this journal; "
                                      "otherwise the sales journal with the lowest sequence is used.")
    tag_ids = fields.Many2many('account.analytic.tag', 'sale_subscription_template_tag_rel', 'template_id', 'tag_id', string='Tags')
    product_count = fields.Integer(compute='_compute_product_count')
    subscription_count = fields.Integer(compute='_compute_subscription_count')
    color = fields.Integer()

    def _compute_subscription_count(self):
        subscription_data = self.env['sale.subscription'].read_group(domain=[('template_id', 'in', self.ids), ('state', 'in', ['open', 'pending'])],
                                                                     fields=['template_id'],
                                                                     groupby=['template_id'])
        mapped_data = dict([(m['template_id'][0], m['template_id_count']) for m in subscription_data])
        for template in self:
            template.subscription_count = mapped_data.get(template.id, 0)

    def _compute_product_count(self):
        product_data = self.env['product.template'].sudo().read_group([('subscription_template_id', 'in', self.ids)], ['subscription_template_id'], ['subscription_template_id'])
        result = dict((data['subscription_template_id'][0], data['subscription_template_id_count']) for data in product_data)
        for template in self:
            template.product_count = result.get(template.id, 0)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        # positive and negative operators behave differently
        if operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            domain = ['|', ('code', operator, name), ('name', operator, name)]
        else:
            domain = ['&', ('code', operator, name), ('name', operator, name)]
        args = args or []
        rec = self.search(domain + args, limit=limit)
        return rec.name_get()

    def name_get(self):
        res = []
        for sub in self:
            name = '%s - %s' % (sub.code, sub.name) if sub.code else sub.name
            res.append((sub.id, name))
        return res
