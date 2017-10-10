# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import models, api

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.multi
    def open_action(self):
        action = super(AccountJournal, self).open_action()
        view = self.env.ref('account.action_invoice_tree2')
        if view and action["id"] == view.id:
            account_purchase_filter = self.env.ref('account_3way_match.account_invoice_filter_inherit_account_3way_match', False)
            action['search_view_id'] = account_purchase_filter and [account_purchase_filter.id, account_purchase_filter.name] or False
        return action

    def _get_open_bills_to_pay_query(self):
        """
        Overriden to take the 'release_to_pay' status into account when getting the
        vendor bills to pay (for other types of journal, its result
        remains unchanged).
        """
        if self.type == 'purchase':
            return ("""SELECT state, amount_total, currency_id AS currency
                   FROM account_invoice
                   WHERE journal_id = %(journal_id)s
                   AND (release_to_pay = 'yes' OR date_due < %(today)s)
                   AND state = 'open';""",
                   {'journal_id':self.id, 'today':datetime.today()})
        return super(AccountJournal, self)._get_open_bills_to_pay_query()

    def _get_bar_graph_select_query(self):
        """
        Overriden to take the 'release_to_pay' status and 'date_due' field into account
        when getting the vendor bills to pay's graph data (for other types of
        journal, its result remains unchanged).
        """
        if self.type == 'purchase':
            return ("""SELECT sum(residual_company_signed) as total, min(date) as aggr_date
                      FROM account_invoice
                      WHERE journal_id = %(journal_id)s
                      AND (release_to_pay = 'yes'
                          OR date_due < %(today)s)
                      AND state = 'open'""",
                      {'journal_id':self.id, 'today':datetime.today()})
        return super(AccountJournal, self)._get_bar_graph_select_query()
