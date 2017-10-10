# -*- coding: utf-8 -*-
import datetime

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, DEFAULT_SERVER_DATE_FORMAT

"""
This module manage an "online account" for a journal. It can't be used in standalone,
other module have to be install (like Plaid or Yodlee). Theses modules must be given
for the online_account reference field. They manage how the bank statement are retrived
from a web service.
"""

class ProviderAccount(models.Model):
    _name = 'account.online.provider'
    _description = 'Provider for online account synchronization'
    _inherit = ['mail.thread']

    name = fields.Char(help='name of the banking institution')
    provider_type = fields.Selection([], readonly=True)
    provider_account_identifier = fields.Char(help='ID used to identify provider account in third party server', readonly=True)
    provider_identifier = fields.Char(readonly=True, help='ID of the banking institution in third party server used for debugging purpose')
    status = fields.Char(string='Synchronization status', readonly=True, help='Update status of provider account')
    status_code = fields.Integer(readonly=True, help='Code to identify problem')
    message = fields.Char(readonly=True, help='Techhnical message from third party provider that can help debugging')
    action_required = fields.Boolean(readonly=True, help='True if user needs to take action by updating account', default=False)
    last_refresh = fields.Datetime(readonly=True)
    next_refresh = fields.Datetime("Next synchronization", compute='_compute_next_synchronization')
    account_online_journal_ids = fields.One2many('account.online.journal', 'account_online_provider_id')
    company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.user.company_id)

    @api.one
    def _compute_next_synchronization(self):
        self.next_refresh = self.env['ir.cron'].sudo().search([('id', '=', self.env.ref('account_online_sync.online_sync_cron').id)], limit=1).nextcall

    @api.multi
    def open_action(self, action_name, number_added):
        action = self.env.ref(action_name).read()[0]
        ctx = self.env.context.copy()
        ctx.update({'default_number_added': number_added})
        action.update({'context': ctx})
        return action

    @api.multi
    def log_message(self, message):
        # Usually when we are eprforming a call to the third party provider to either refresh/fetch transaction/add user, etc,
        # the call can fail and we raise an error. We also want the error message to be logged in the object in the case the call
        # is done by a cron. This is why we are using a separate cursor to write the information on the chatter. Otherwise due to
        # the raise(), the transaction would rollback and nothing would be posted on the chatter.
        # There is a particuler use case with this, is when we are trying to unlink an account.online.provider,
        # we usually also perform a call to the third party provider to delete it from the third party provider system.
        # This call can also fail and if this is the case we do not want to prevent the user from deleting the object in odoo.
        # Problem is that if we try to log the error message, it will result in an error since a transaction will delete the object
        # and another transaction will try to write on the object. Therefore, we need to pass a special key in the context in those
        # cases to prevent writing on the object
        if not self._context.get('no_post_message'):
            subject = _("An error occurred during online synchronization")
            message = _('The following error happened during the synchronization: %s' % (message,))
            with self.pool.cursor() as cr:
                self.with_env(self.env(cr=cr)).message_post(body=message, subject=subject)

    """ Methods that need to be override by sub-module"""

    @api.multi
    def get_institution(self, searchString):
        """ This method should return a list of institution based on a searchString
            Each element of the list should be a dictionaries with the following key:
            'id': the id of the institution in the third party provider system
            'name': the name of the institution
            'status': wheter the institution is fully supported by the third party provider or not
            'countryISOCode': code of the country the institution is located in
            'baseUrl': url of the banking institution
            'loginUrl': url of the login page of the banking institution
            'type_provider': the type of the provider (yodlee or plaid for example)
        """
        return []

    @api.multi
    def get_login_form(self, site_id, provider):
        """ This method is used to fetch and display the login form of the institution choosen in
            get_institution method. Usually this method should return a client action that will
            render the login form
        """
        return []

    @api.multi
    def manual_sync(self):
        """ This method is used to ask the third party provider to refresh the account and
            fetch the latest transactions.
        """
        return False


class OnlineAccount(models.Model):
    """
    This class is used as an interface.
    It is used to save the state of the current online accout.
    """
    _name = 'account.online.journal'
    _description = 'Interface for online account journal'

    name = fields.Char(required=True)
    account_online_provider_id = fields.Many2one('account.online.provider', ondelete='cascade', readonly=True)
    journal_ids = fields.One2many('account.journal', 'account_online_journal_id', string='Journal', domain=[('type', '=', 'bank')])
    account_number = fields.Char()
    last_sync = fields.Date("Last synchronization")
    online_identifier = fields.Char(help='id use to identify account in provider system', readonly=True)
    provider_name = fields.Char(related='account_online_provider_id.name', readonly=True)
    balance = fields.Float(readonly=True, help='balance of the account sent by the third party provider')

    @api.multi
    @api.depends('name', 'account_online_provider_id.name')
    def name_get(self):
        res = []
        for account_online in self:
            name = "%s: %s" % (account_online.provider_name, account_online.name)
            if account_online.account_number:
                name += " (%s)" % (account_online.account_number)
            res += [(account_online.id, name)]
        return res

    @api.multi
    def retrieve_transactions(self):
        # This method must be implemented by plaid and yodlee services
        raise UserError(_("Unimplemented"))

class OnlineAccountWizard(models.TransientModel):
    _name = 'account.online.wizard'
    _description = 'Wizard for online account synchronization'

    journal_id = fields.Many2one('account.journal')
    account_online_journal_id = fields.Many2one('account.online.journal', string='Online account', domain=[('journal_ids', '=', False)])
    sync_date = fields.Date('Fetch transaction from')
    number_added = fields.Char(help='number of accounts added from call to new_institution', readonly=True)
    count_account_online_journal = fields.Integer(compute='_count_account_online_journal', help="technical field used to hide account_online_journal_id if no institution has been loaded in the system")

    @api.multi
    @api.depends('journal_id')
    def _count_account_online_journal(self):
        for wizard in self:
            wizard.count_account_online_journal = self.env['account.online.journal'].search_count([('journal_ids', '=', False)])

    @api.onchange('account_online_journal_id')
    def onchange_account_online_journal_id(self):
        if self.account_online_journal_id:
            self.sync_date = self.account_online_journal_id.last_sync

    @api.multi
    def configure(self):
        journal_id = self._context.get('active_id')
        self.journal_id = self.env['account.journal'].browse(journal_id)
        self.journal_id.write({'account_online_journal_id': self.account_online_journal_id.id, 'bank_statements_source': 'online_sync'})
        if self.sync_date:
            self.account_online_journal_id.write({'last_sync': self.sync_date})
        action = self.env.ref('account.open_account_journal_dashboard_kanban').read()[0]
        return action

    @api.multi
    def new_institution(self):
        ctx = self.env.context.copy()
        ctx.update({'open_action_end': 'account_online_sync.action_account_online_wizard_form'})
        return self.env['account.journal'].with_context(ctx).action_choose_institution()

class AccountJournal(models.Model):
    _inherit = "account.journal"

    bank_statements_source = fields.Selection(selection_add=[("online_sync", "Bank Synchronization")])
    next_synchronization = fields.Datetime("Next synchronization", compute='_compute_next_synchronization')
    account_online_journal_id = fields.Many2one('account.online.journal', string='Online Account')
    account_online_provider_id = fields.Many2one('account.online.provider', related='account_online_journal_id.account_online_provider_id')
    synchronization_status = fields.Char(related='account_online_provider_id.status')
    bank_statement_creation = fields.Selection([('none', 'Create one statement per synchronization'),
                                                ('day', 'Create daily statements'),
                                                ('week', 'Create weekly statements'),
                                                ('bimonthly', 'Create bi-monthly statements'),
                                                ('month', 'Create monthly statements')],
                                               help="""This field is used for the online synchronization:
                                                    depending on the option selected, newly fetched transactions
                                                    will be put inside previous statement or in a new one""",
                                               default='none',
                                               string='Creation of bank statement')

    @api.one
    def _compute_next_synchronization(self):
        self.next_synchronization = self.env['ir.cron'].sudo().search([('id', '=', self.env.ref('account_online_sync.online_sync_cron').id)], limit=1).nextcall

    @api.multi
    def action_choose_institution(self):
        ctx = self.env.context.copy()
        ctx.update({'show_select_button': True})
        return {
                'type': 'ir.actions.client',
                'tag': 'online_sync_institution_selector',
                'target': 'new',
                'context': ctx,
                }

    @api.multi
    def manual_sync(self):
        if self.account_online_journal_id:
            return self.account_online_journal_id.account_online_provider_id.manual_sync()

    @api.model
    def cron_fetch_online_transactions(self):
        for account in self.search([('account_online_journal_id', '!=', False)]):
            try:
                account.account_online_provider_id.cron_fetch_online_transactions()
            except UserError:
                continue


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    @api.model
    def online_sync_bank_statement(self, transactions, journal):
        """
         build a bank statement from a list of transaction and post messages is also post in the online_account of the journal.
         :param transactions: A list of transactions that will be created in the new bank statement.
             The format is : [{
                 'id': online id,                  (unique ID for the transaction)
                 'date': transaction date,         (The date of the transaction)
                 'description': transaction description,  (The description)
                 'amount': transaction amount,     (The amount of the transaction. Negative for debit, positive for credit)
                 'end_amount': total amount on the account
                 'location': optional field used to find the partner (see _find_partner for more info)
             }, ...]
         :param journal: The journal (account.journal) of the new bank statement

         Return: The number of imported transaction for the journal
        """
        # Since the synchronization succeeded, set it as the bank_statements_source of the journal
        journal.bank_statements_source = 'online_sync'

        all_lines = self.env['account.bank.statement.line'].search([('journal_id', '=', journal.id),
                                                                    ('date', '>=', journal.account_online_journal_id.last_sync)])
        total = 0
        lines = []
        last_date = journal.account_online_journal_id.last_sync
        end_amount = 0
        for transaction in transactions:
            if all_lines.search_count([('online_identifier', '=', transaction['id'])]) > 0 or transaction['amount'] == 0.0:
                continue
            line = {
                'date': transaction['date'],
                'name': transaction['description'],
                'amount': transaction['amount'],
                'online_identifier': transaction['id'],
            }
            total += transaction['amount']
            end_amount = transaction['end_amount']
            # Partner from address
            if 'location' in transaction:
                line['partner_id'] = self._find_partner(transaction['location'])
            # Get the last date
            if not last_date or transaction['date'] > last_date:
                last_date = transaction['date']
            lines.append((0, 0, line))

        # Search for previous transaction end amount
        previous_statement = self.search([('journal_id', '=', journal.id)], order="date desc, id desc", limit=1)
        # For first synchronization, an opening bank statement line is created to fill the missing bank statements
        all_statement = self.search_count([('journal_id', '=', journal.id)])
        if all_statement == 0 and end_amount - total != 0:
            lines.append((0, 0, {
                'date': transactions and (transactions[0]['date']) or datetime.datetime.now(),
                'name': _("Opening statement: first synchronization"),
                'amount': end_amount - total,
            }))
            total = end_amount

        # If there is no new transaction, the bank statement is not created
        if lines:
            to_create = []
            # Depending on the option selected on the journal, either create a new bank statement or add lines to existing bank statement.
            previous_amount_to_report = 0
            for line in lines:
                create = False
                if not previous_statement or previous_statement.state == 'confirm':
                    to_create = lines
                    break
                line_date = datetime.datetime.strptime(line[2]['date'], DEFAULT_SERVER_DATE_FORMAT)
                p_stmt = datetime.datetime.strptime(previous_statement.date, DEFAULT_SERVER_DATE_FORMAT)
                if journal.bank_statement_creation == 'day' and previous_statement.date != line[2]['date']:
                    create = True
                elif journal.bank_statement_creation == 'week' and line_date.isocalendar()[1] != p_stmt.isocalendar()[1]:
                    create = True
                elif journal.bank_statement_creation == 'bimonthly':
                    if (line_date.month != p_stmt.month or line_date.year != p_stmt.year):
                        create = True
                    elif line_date.day > 15 and p_stmt.day <= 15:
                        create = True
                elif journal.bank_statement_creation == 'month' and (line_date.month != p_stmt.month or line_date.year != p_stmt.year):
                    create = True
                elif not journal.bank_statement_creation or journal.bank_statement_creation == 'none':
                    create = True

                if create:
                    to_create.append(line)
                else:
                    previous_amount_to_report += line[2]['amount']
                    line[2].update({'statement_id': previous_statement.id})
                    self.env['account.bank.statement.line'].create(line[2])

            if not float_is_zero(previous_amount_to_report, precision_rounding=journal.currency_id.rounding):
                previous_statement.write({'balance_end_real': previous_statement.balance_end_real + previous_amount_to_report})

            if to_create:
                balance_start = None
                if previous_statement:
                    balance_start = previous_statement.balance_end_real
                sum_lines = sum([l[2]['amount'] for l in to_create])
                self.create({'name': _('online sync'),
                            'journal_id': journal.id,
                            'line_ids': to_create,
                            'balance_end_real': end_amount if balance_start is None else balance_start + sum_lines,
                            'balance_start': (end_amount - total) if balance_start is None else balance_start
                            })

        journal.account_online_journal_id.last_sync = last_date
        return len(lines)

    @api.model
    def _find_partner(self, location):
        """
        Return a recordset of partner if the address of the transaction exactly match the address of a partner
        location : a dictionary of type:
                   {'state': x, 'address': y, 'city': z, 'zip': w}
                   state and zip are optional

        """
        partners = self.env['res.partner']
        domain = []
        if 'address' in location and 'city' in location:
            domain.append(('street', '=', location['address']))
            domain.append(('city', '=', location['city']))
            if 'state' in location:
                domain.append(('state_id.name', '=', location['state']))
            if 'zip' in location:
                domain.append(('zip', '=', location['zip']))
            return partners.search(domain, limit=1)
        return partners

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    online_identifier = fields.Char("Online Identifier")
