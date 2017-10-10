# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AccountBatchDeposit(models.Model):
    _name = "account.batch.deposit"
    _description = "Batch Deposit"
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, string='Reference', readonly=True, states={'draft': [('readonly', False)]})
    date = fields.Date(required=True, copy=False, default=fields.Date.context_today, readonly=True, states={'draft': [('readonly', False)]})
    state = fields.Selection([('draft', 'New'), ('sent', 'Printed'), ('reconciled', 'Reconciled')], readonly=True, default='draft', copy=False)
    journal_id = fields.Many2one('account.journal', string='Bank', domain=[('type', '=', 'bank')], required=True, readonly=True, states={'draft': [('readonly', False)]})
    payment_ids = fields.One2many('account.payment', 'batch_deposit_id', string="Payments", required=True, readonly=True, states={'draft': [('readonly', False)]})
    amount = fields.Monetary(compute='_compute_amount', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency', store=True, readonly=True)

    @api.one
    @api.depends('journal_id')
    def _compute_currency(self):
        if self.journal_id:
            self.currency_id = self.journal_id.currency_id or self.journal_id.company_id.currency_id
        else:
            self.currency_id = False

    @api.one
    @api.depends('payment_ids', 'journal_id')
    def _compute_amount(self):
        company_currency = self.journal_id.company_id.currency_id or self.env.user.company_id.currency_id
        journal_currency = self.journal_id.currency_id or company_currency
        amount = 0
        for payment in self.payment_ids:
            payment_currency = payment.currency_id or company_currency
            if payment_currency == journal_currency:
                amount += payment.amount
            else:
                # Note : this makes self.date the value date, which IRL probably is the date of the reception by the bank
                amount += payment_currency.with_context({'date': self.date}).compute(payment.amount, journal_currency)
        self.amount = amount

    @api.one
    @api.constrains('journal_id', 'payment_ids')
    def _check_same_journal(self):
        if not self.journal_id:
            return
        if any(payment.journal_id != self.journal_id for payment in self.payment_ids):
            raise ValidationError("The journal of the batch deposit and of the payments it contains must be the same.")

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            journal_id = vals.get('journal_id', self.env.context.get('default_journal_id', False))
            journal = self.env['account.journal'].browse(journal_id)
            vals['name'] = journal.batch_deposit_sequence_id.with_context(ir_sequence_date=vals.get('date')).next_by_id()
        rec = super(AccountBatchDeposit, self).create(vals)
        rec.normalize_payments()
        return rec

    @api.multi
    def write(self, vals):
        super(AccountBatchDeposit, self).write(vals)
        self.normalize_payments()

    @api.one
    def normalize_payments(self):
        # Make sure all payments have batch_deposit as payment method (a payment created via the form view of the
        # payment_ids many2many of the batch deposit form view cannot receive a default_payment_method in context)
        self.payment_ids.write({'payment_method_id': self.env.ref('account_batch_deposit.account_payment_method_batch_deposit').id})
        # Since a batch deposit has no confirmation step (it can be used to select payments in a bank reconciliation
        # as long as state != reconciled), its payments need to be posted
        self.payment_ids.filtered(lambda r: r.state == 'draft').post()

    @api.multi
    def print_batch_deposit(self):
        for deposit in self:
            if deposit.state != 'draft':
                continue
            deposit.payment_ids.write({'state': 'sent', 'payment_reference': deposit.name})
            deposit.write({'state': 'sent'})
        return self.env.ref('account_batch_deposit.action_print_batch_deposit').report_action(self)
