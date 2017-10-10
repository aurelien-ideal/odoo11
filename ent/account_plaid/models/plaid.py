# -*- coding: utf-8 -*-
import requests
import json
import datetime
import logging

from odoo import models, api, fields
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)

class PlaidProviderAccount(models.Model):
    _inherit = ['account.online.provider']

    provider_type = fields.Selection(selection_add=[('plaid', 'Plaid')])

    def _get_plaid_credentials(self):
        ICP_obj = self.env['ir.config_parameter'].sudo()
        login = ICP_obj.get_param('plaid_id') or self._cr.dbname
        secret = ICP_obj.get_param('plaid_secret') or ICP_obj.get_param('database.uuid')
        url = ICP_obj.get_param('plaid_service_url') or 'https://onlinesync.odoo.com/plaid/api'
        return {'login': login, 'secret': secret, 'url': url,}

    def check_plaid_error(self, resp):
        try:
            resp_json = resp.json()
            if type(resp_json) == dict and resp_json.get('code') and resp.status_code >= 400:
                message = resp_json.get('message')+' ('+str(resp_json.get('code'))+'): '+resp_json.get('resolve')
                self.update_status('FAILED', resp_json.get('code'), resp_json.get('message')+': '+resp_json.get('resolve'))
                self.log_message(message)
                raise UserError(message)
            elif resp.status_code in (400, 403):
                # This is the error coming back from odoo proxy like user not having valid contract
                self.update_status('FAILED', 0, resp.text)
                self.log_message(resp.text)
                raise UserError(resp.text)
            resp.raise_for_status()
        except (requests.HTTPError, ValueError):
            self.update_status('FAILED')
            message = _('Get %s status code for call to %s. Content message: %s' % (resp.status_code, resp.url, resp.text))
            self.log_message(message)
            raise UserError(message)

    @api.multi
    def plaid_fetch(self, url, params, data, type_request="POST"):
        credentials = self._get_plaid_credentials()
        url = credentials['url'] + url
        try:
            # The only get request we have for plaid are to fetch institution and they don't need credentials for that
            if type_request == 'GET':
                resp = requests.get(url, params=params, data=data, timeout=30)
            data['client_id'] = credentials['login']
            data['secret'] = credentials['secret']
            # If we find update in context, it means we are trying to update user information, so a patch must be done, not a post
            # We also need to add the access token in the request
            if type_request == 'POST' and self._context.get('update', False):
                type_request = 'PATCH'
                data['access_token'] = self.provider_account_identifier
            if type_request == 'POST':
                resp = requests.post(url, params=params, data=data, timeout=30)
            elif type_request == 'PATCH':
                resp = requests.patch(url, params=params, data=data, timeout=30)
            elif type_request == 'DELETE':
                resp = requests.delete(url, params=params, data=data, timeout=30)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        self.check_plaid_error(resp)
        return (resp.status_code, resp.json())

    @api.multi
    def get_institution(self, searchString):
        ret = super(PlaidProviderAccount, self).get_institution(searchString)
        (status, resp_json) = self.plaid_fetch('/institutions', {}, {}, 'GET')
        for institution in resp_json:
            if searchString.lower() in institution.get('name','').lower():
                ret.append({'id': institution.get('id'),
                        'name': institution.get('name'),
                        'status': 'Supported',
                        'countryISOCode': '',
                        'baseUrl': '/',
                        'loginUrl': '/',
                        'type_provider': 'plaid',
                        'type': institution.get('type')})
        return sorted(ret, key=lambda p: p.get('countryISOCode', 'AA'))

    @api.multi
    def get_login_form(self, site_id, provider):
        if provider != 'plaid':
            return super(PlaidProviderAccount, self).get_login_form(site_id, provider)
        (status, resp_json) = self.plaid_fetch('/institutions/'+str(site_id), {}, {}, 'GET')
        return {
                'type': 'ir.actions.client',
                'tag': 'plaid_online_sync_widget',
                'target': 'new',
                'site_info': resp_json,
                'context': self.env.context,
                }

    @api.multi
    def update_status(self, status, code=None, message=None):
        if not code:
            code = 0
        if not message:
            message = ''
        with self.pool.cursor() as cr:
            self = self.with_env(self.env(cr=cr)).write({'status': status, 'status_code': code, 'last_refresh': fields.Datetime.now(),})

    @api.multi
    def plaid_add_update_provider_account(self, values, site_id, name, mfa=False):
        if not mfa:
            (status, resp_json) = self.plaid_fetch('/connect', {}, values, 'POST')

            # We create a new online_provider_account if there isn't one with the same token
            provider_account = self.search([('provider_account_identifier', '=', resp_json.get('access_token')), ('company_id', '=', self.env.user.company_id.id)], limit=1)
            if len(provider_account) == 0:
                vals = {'name': name or 'Online institution', 
                    'provider_account_identifier': resp_json.get('access_token'),
                    'provider_identifier': site_id,
                    'status': 'IN_PROGRESS',
                    'status_code': 0,
                    'message': '',
                    'last_refresh': fields.Datetime.now(),
                    'provider_type': 'plaid',
                    }
                with self.pool.cursor() as cr:
                    new_id = self.with_env(self.env(cr=cr)).create(vals)
                    self = self.browse(new_id)
            else:
                provider_account.update_status('IN_PROGRESS')
                self = provider_account
        else:
            (status, resp_json) = self.plaid_fetch('/connect/step', {}, values, 'POST')

        # Check status code to see if we have to show mfa or not
        if status == 201:
            # Recquire MFA
            resp_json['action'] = 'mfa'
            resp_json['account_online_provider_id'] = self.id
            return resp_json
        else:
            # Success, add account to odoo
            self.update_status('SUCCESS')
            account_added = self.plaid_add_update_account(resp_json)
            return {'action': 'success', 'numberAccountAdded': len(account_added)}

    @api.multi
    def plaid_add_update_account(self, resp_json):
        account_added = self.env['account.online.journal']
        for account in resp_json.get('accounts', []):
            vals = {'balance': account.get('balance', {}).get('current'),}
            account_search = self.env['account.online.journal'].search([('account_online_provider_id', '=', self.id), ('online_identifier', '=', account.get('_id'))], limit=1)
            if len(account_search) == 0:
                dt = datetime.datetime
                last_sync = dt.strftime(dt.strptime(self.last_refresh, DEFAULT_SERVER_DATETIME_FORMAT) - datetime.timedelta(days=15), DEFAULT_SERVER_DATE_FORMAT)
                vals.update({'name': account.get('meta', {}).get('name', 'Account'),
                        'account_online_provider_id': self.id,
                        'online_identifier': account.get('_id'),
                        'account_number': account.get('meta', {}).get('number'),
                        'last_sync': last_sync})
                with self.pool.cursor() as cr:
                    acc = self.with_env(self.env(cr=cr)).env['account.online.journal'].create(vals)
                account_added += acc
            else:
                with self.pool.cursor() as cr:
                    account_search.with_env(self.env(cr=cr)).env['account.online.journal'].write(vals)
        return account_added

    @api.multi
    def manual_sync(self):
        if self.provider_type != 'plaid':
            return super(PlaidProviderAccount, self).manual_sync()
        self.update_status('SUCCESS')
        transactions = []
        for account in self.account_online_journal_ids:
            if account.journal_ids:
                tr = account.retrieve_transactions()
                transactions.append({'journal': account.journal_ids[0].name, 'count': tr})
        resp_json = {'action': 'success', 'transactions': transactions}
        ctx = dict(self._context or {})
        ctx.update({'init_call': False, 'provider_account_identifier': self.id})
        return {
                'type': 'ir.actions.client',
                'tag': 'plaid_online_sync_widget',
                'target': 'new',
                'resp_json': resp_json,
                'context': ctx,
                }

    @api.multi
    def update_credentials(self):
        if self.provider_type != 'plaid':
            return super(PlaidProviderAccount, self).update_credentials()
        ret_action = self.get_login_form(self.provider_identifier, 'plaid')
        ctx = dict(self._context or {})
        ctx.update({'update': True, 'provider_account_identifier': self.id})
        ret_action['context'] = ctx
        return ret_action

    @api.model
    def cron_fetch_online_transactions(self):
        if self.provider_type != 'plaid':
            return super(PlaidProviderAccount, self).cron_fetch_online_transactions()
        self.manual_sync()

    @api.multi
    def unlink(self):
        for provider in self:
            if provider.provider_type == 'plaid':
                # call yodlee to ask to remove link between user and provider_account_identifier
                try:
                    data = {'access_token': provider.provider_account_identifier}
                    ctx = self._context.copy()
                    ctx['no_post_message'] = True
                    provider.with_context(ctx).plaid_fetch('/connect', {}, data, 'DELETE')
                except UserError:
                    # If call to fails, don't prevent user to delete record 
                    pass
        super(PlaidProviderAccount, self).unlink()

class PlaidAccount(models.Model):
    _inherit = 'account.online.journal'

    @api.multi
    def retrieve_transactions(self):
        if (self.account_online_provider_id.provider_type != 'plaid'):
            return super(PlaidAccount, self).retrieve_transactions()
        # Fetch plaid.com
        # For all transactions since the last synchronization, for this journal
        params = {
            'access_token': self.account_online_provider_id.provider_account_identifier,
            'options': '{"gte": "' + self.last_sync + '", "account": "' + self.online_identifier + '"}',
        }
        transactions = []
        (status_code, resp_json) = self.account_online_provider_id.plaid_fetch('/connect/get', {}, params, 'POST')
        if status_code == 200:
            # Update the balance
            for account in resp_json['accounts']:
                if account['_id'] == self.online_identifier:
                    end_amount = account['balance']['current']
            # Prepare the transaction
            for transaction in resp_json['transactions']:
                trans = {
                    'id': transaction['_id'],
                    'date': transaction['date'],
                    'description': transaction['name'],
                    'amount': -1 * transaction['amount'],
                    'end_amount': end_amount,
                }
                if 'meta' in transaction and 'location' in transaction['meta']:
                    trans['location'] = transaction['meta']['location']
                transactions.append(trans)
            # Create the bank statement with the transactions
        return self.env['account.bank.statement'].online_sync_bank_statement(transactions, self.journal_ids[0])
