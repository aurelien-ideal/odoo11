# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api
from odoo.tools.misc import formatLang


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    @api.multi
    def reconciliation_widget_preprocess(self):
        """ Add batch deposits data to the dict returned """
        res = super(AccountBankStatement, self).reconciliation_widget_preprocess()
        res.update({'batch_deposits': self.get_batch_deposits_data()})
        return res

    @api.multi
    def get_batch_deposits_data(self):
        """ Return a list of dicts containing informations about unreconciled batch deposits """
        batch_deposits = []

        batch_deposits_domain = [('state', '!=', 'reconciled')]
        if self:
            # If called on an empty recordset, don't filter on journal
            batch_deposits_domain.append(('journal_id', 'in', tuple(set(self.mapped('journal_id.id')))))

        for batch_deposit in self.env['account.batch.deposit'].search(batch_deposits_domain, order='id asc'):
            payments = batch_deposit.payment_ids
            journal = batch_deposit.journal_id
            company_currency = journal.company_id.currency_id
            journal_currency = journal.currency_id or company_currency

            amount_journal_currency = formatLang(self.env, batch_deposit.amount, currency_obj=journal_currency)
            amount_deposit_currency = False
            # If all the payments of the deposit are in another currency than the journal currency, we'll display amount in both currencies
            if payments and all(p.currency_id != journal_currency and p.currency_id == payments[0].currency_id for p in payments):
                amount_deposit_currency = sum(p.amount for p in payments)
                amount_deposit_currency = formatLang(self.env, amount_deposit_currency, currency_obj=payments[0].currency_id or company_currency)

            batch_deposits.append({
                'id': batch_deposit.id,
                'name': batch_deposit.name,
                'journal_id': journal.id,
                'amount_str': amount_journal_currency,
                'amount_currency_str': amount_deposit_currency,
            })
        return batch_deposits


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    @api.multi
    def get_move_lines_for_reconciliation_widget_by_batch_deposit_id(self, batch_deposit_id):
        """ As get_move_lines_for_reconciliation_widget, but returns lines from a batch deposit """
        self.ensure_one()
        payments = self.env['account.batch.deposit'].browse(batch_deposit_id).payment_ids
        move_lines = payments.mapped('move_line_ids').filtered(lambda r: r.account_id.internal_type == 'liquidity')
        target_currency = self.currency_id or self.journal_id.currency_id or self.journal_id.company_id.currency_id
        return move_lines.prepare_move_lines_for_reconciliation_widget(target_currency=target_currency, target_date=self.date)
