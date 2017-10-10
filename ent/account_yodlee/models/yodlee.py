# -*- coding: utf-8 -*-
import math
import requests
import json
import datetime
import time
import logging
import uuid
import json
import re

from odoo import models, api, fields
from odoo.exceptions import UserError
from odoo.tools.translate import _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class YodleeProviderAccount(models.Model):
    _inherit = ['account.online.provider']

    yodlee_additional_status = fields.Char(readonly=True, help='Additional information on status')
    yodlee_last_attempted_refresh = fields.Datetime(readonly=True)
    yodlee_next_schedule_refresh = fields.Datetime(help='Technical field: scheduled time for yodlee to perform an update')
    provider_type = fields.Selection(selection_add=[('yodlee', 'Yodlee')])

    @api.model
    def _get_yodlee_credentials(self):
        ICP_obj = self.env['ir.config_parameter'].sudo()
        login = ICP_obj.get_param('yodlee_id') or self._cr.dbname
        secret = ICP_obj.get_param('yodlee_secret') or ICP_obj.get_param('database.uuid')
        url = ICP_obj.get_param('yodlee_service_url') or 'https://onlinesync.odoo.com/yodlee/api/2'
        return {'login': login, 'secret': secret, 'url': url,}

    @api.multi
    def register_new_user(self):
        company_id = self.env.user.company_id
        username = self.env.registry.db_name + '_' + str(uuid.uuid4())

        # Implement funky password policy from Yodlee's REST API
        password = str(uuid.uuid4()).upper().replace('-','#')
        while re.search(r'(.)\1\1', password):
            password = str(uuid.uuid4()).upper().replace('-','#')

        email = company_id.partner_id.email
        if not email:
            raise UserError(_('Please configure an email in the company settings.'))
        credentials = self._get_yodlee_credentials()
        self.do_cobrand_login()
        headerVal = {'Authorization': '{cobSession='+company_id.yodlee_access_token+'}'}
        requestBody = json.dumps(
            {'user': {'loginName': username,
                      'password': password,
                      'email': email}}
        )
        try:
            resp = requests.post(url=credentials['url']+'/user/register', data=requestBody, headers=headerVal, timeout=30)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        self.check_yodlee_error(resp)
        company_id.yodlee_user_access_token = resp.json().get('user').get('session').get('userSession')
        company_id.yodlee_user_login = username
        company_id.yodlee_user_password = password       

    @api.multi
    def do_cobrand_login(self):
        credentials = self._get_yodlee_credentials()
        requestBody = {'cobrandLogin': credentials['login'], 'cobrandPassword': credentials['secret']}
        try:
            resp = requests.post(url=credentials['url']+'/cobrand/login', data=requestBody, timeout=30)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        self.check_yodlee_error(resp)
        company_id = self.company_id or self.env.user.company_id
        company_id.yodlee_access_token = resp.json().get('session').get('cobSession')

    @api.multi
    def do_user_login(self):
        credentials = self._get_yodlee_credentials()
        company_id = self.company_id or self.env.user.company_id
        headerVal = {'Authorization': '{cobSession='+company_id.yodlee_access_token+'}'}
        requestBody = {'loginName': company_id.yodlee_user_login, 'password': company_id.yodlee_user_password}
        try:
            resp = requests.post(url=credentials['url']+'/user/login', data=requestBody, headers=headerVal, timeout=30)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        self.check_yodlee_error(resp)
        company_id.yodlee_user_access_token = resp.json().get('user').get('session').get('userSession')

    @api.multi
    def get_auth_tokens(self):
        self.do_cobrand_login()
        self.do_user_login()

    def check_yodlee_error(self, resp):
        try:
            resp_json = resp.json()
            if resp_json.get('errorCode'):
                if resp.json().get('errorCode') in ('Y007', 'Y008', 'Y009', 'Y010'):
                    return 'invalid_auth'
                message = _('Error %s, message: %s, reference code: %s' % (resp_json.get('errorCode'), resp_json.get('errorMessage'), resp_json.get('referenceCode')))
                message = ("%s\n\n" + _('(Diagnostic: %r for URL %s)')) % (message, resp.status_code, resp.url)
                self.log_message(message)
                raise UserError(message)
            resp.raise_for_status()
        except (requests.HTTPError, ValueError):
            message = ('%s\n\n' + _('(Diagnostic: %r for URL %s)')) % (resp.text.strip(), resp.status_code, resp.url)
            self.log_message(message)
            raise UserError(message)

    @api.multi
    def yodlee_fetch(self, url, params, data, type_request='POST'):
        credentials = self._get_yodlee_credentials()
        company_id = self.company_id or self.env.user.company_id
        service_url = url
        url = credentials['url'] + url
        if not company_id.yodlee_user_login:
            self.register_new_user()
        if not company_id.yodlee_access_token or not company_id.yodlee_user_access_token:
            self.get_auth_tokens()
        headerVal = {'Authorization': '{cobSession='+company_id.yodlee_access_token+', userSession='+company_id.yodlee_user_access_token+'}'}
        try:
            if type_request == 'POST':
                resp = requests.post(url=url, params=params, data=data, headers=headerVal, timeout=30)
            elif type_request == 'GET':
                resp = requests.get(url=url, params=params, data=data, headers=headerVal, timeout=30)
            elif type_request == 'PUT':
                resp = requests.put(url=url, params=params, data=data, headers=headerVal, timeout=30)
            elif type_request == 'DELETE':
                resp = requests.delete(url=url, params=params, data=data, headers=headerVal, timeout=30)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        # Manage errors and get new token if needed
        if self.check_yodlee_error(resp) == 'invalid_auth':
            self.get_auth_tokens()
            return self.yodlee_fetch(service_url, params, data, type_request=type_request)
        return resp.json()

    @api.multi
    def get_institution(self, searchString):
        # get_provider()
        ret = super(YodleeProviderAccount, self).get_institution(searchString)
        if len(searchString) < 3:
            raise UserError(_('Please enter at least 3 characters for the search'))
        requestBody = {'name': searchString}
        resp_json = self.yodlee_fetch('/providers', requestBody, {}, 'GET')
        providers = resp_json.get('provider', [])
        for provider in providers:
            provider['type_provider'] = 'yodlee'
        providers.extend(ret)
        return sorted(providers, key=lambda p: p.get('countryISOCode', 'AA'))

    @api.multi
    def get_login_form(self, site_id, provider):
        if provider != 'yodlee':
            return super(YodleeProviderAccount, self).get_login_form(site_id, provider)
        resp_json = self.yodlee_fetch('/providers/'+str(site_id), {}, {}, 'GET')
        if not resp_json:
            raise UserError(_('Could not retrieve login form for siteId: %s (%s)' % (site_id, provider)))
        return {
                'type': 'ir.actions.client',
                'tag': 'yodlee_online_sync_widget',
                'target': 'new',
                'login_form': resp_json,
                'context': self.env.context,
                }

    @api.multi
    def update_credentials(self):
        if self.provider_type != 'yodlee':
            return super(YodleeProviderAccount, self).update_credentials()
        return_action = self.get_login_form(self.provider_identifier, 'yodlee')
        ctx = dict(self._context or {})
        ctx.update({'init_call': False, 'provider_account_identifier': self.id})
        return_action['context'] = ctx
        return return_action

    def convert_date_from_yodlee(self, date):
        if not date:
            return fields.Datetime.now()
        dt = datetime.datetime
        return dt.strftime(dt.strptime(date, '%Y-%m-%dT%H:%M:%SZ'), DEFAULT_SERVER_DATETIME_FORMAT)

    @api.multi
    def yodlee_add_update_provider_account(self, values, site_id, name=None):
        # Setting values entered by user into json
        fields = []
        if type(values) != list:
            # most call to /providerAccounts only needs a dict with id, value keys
            # only exception is for type: questionAndAnswer which require a special format
            # the case is handle in javascript and js pass a dict as values instead of a list
            # in that particular case
            data = json.dumps({'loginForm': values})
        else:
            for element in values:
                if element.get('required', True) == 'false' and element['value'] == '':
                    raise UserError(_('Please fill all required fields'))
                if element['value'] != '':
                    fields.append({'id': element['field_id'], 'value': element['value']})
            data = json.dumps({'field': fields}) if len(fields) > 0 else []
        params = {'providerId': site_id}
        # If we have an id, it means that provider_account already exists and that it is an update
        if len(self) > 0 and self.id:
            params = {'providerAccountIds': self.provider_account_identifier}
            resp_json = self.yodlee_fetch('/providerAccounts', params, data, 'PUT')
            return self.id
        else:
            resp_json = self.yodlee_fetch('/providerAccounts', params, data, 'POST')
            refresh_info = resp_json.get('providerAccount', {}).get('refreshInfo')
            provider_account_identifier = resp_json.get('providerAccount', {}).get('id')
            vals = {'name': name or 'Online institution', 
                    'provider_account_identifier': provider_account_identifier,
                    'provider_identifier': site_id,
                    'status': refresh_info.get('status'),
                    'yodlee_additional_status': refresh_info.get('additionalStatus'),
                    'status_code': refresh_info.get('statusCode'),
                    'message': refresh_info.get('statusMessage'),
                    'action_required': refresh_info.get('actionRequired', False),
                    'last_refresh': self.convert_date_from_yodlee(refresh_info.get('lastRefreshed')),
                    'yodlee_last_attempted_refresh': self.convert_date_from_yodlee(refresh_info.get('lastRefreshAttempt')),
                    'provider_type': 'yodlee',
                    }

            # We create a new object if there isn't one with the same provider_account_identifier
            new_provider_account = self.search([('provider_account_identifier', '=', provider_account_identifier), ('company_id', '=', self.env.user.company_id.id)], limit=1)
            if len(new_provider_account) == 0:
                with self.pool.cursor() as cr:
                    new_provider_account = self.with_env(self.env(cr=cr)).create(vals)
            return new_provider_account.id

    @api.multi
    def manual_sync(self, return_action=True):
        if self.provider_type != 'yodlee':
            return super(YodleeProviderAccount, self).manual_sync()
        # trigger update
        params = {'providerAccountIds': self.provider_account_identifier}
        resp_json = self.yodlee_fetch('/providerAccounts', params, {}, 'PUT')
        # Wait for refresh to finish and reply with mfa token
        resp_json = self.refresh_status()
        if not return_action:
            return resp_json
        ctx = dict(self._context or {})
        ctx.update({'init_call': False, 'provider_account_identifier': self.id})
        return {
            'type': 'ir.actions.client',
            'tag': 'yodlee_online_sync_widget',
            'target': 'new',
            'refresh_info': resp_json,
            'context': ctx,
        }

    @api.multi
    def write_status(self, refresh_info):
        vals = {
            'status': refresh_info.get('status'),
            'yodlee_additional_status': refresh_info.get('additionalStatus') or refresh_info.get('additionalInfo'),
            'status_code': refresh_info.get('statusCode'),
            'message': refresh_info.get('statusMessage'),
            'action_required': refresh_info.get('actionRequired', False),
            'last_refresh': self.convert_date_from_yodlee(refresh_info.get('lastRefreshed')),
            'yodlee_last_attempted_refresh': self.convert_date_from_yodlee(refresh_info.get('lastRefreshAttempt')),
            'yodlee_next_schedule_refresh': self.convert_date_from_yodlee(refresh_info.get('nextRefreshScheduled')),
        }
        # We want a new cursor to write the transaction because if there is an error (like invalid credentials)
        # we want it to be written on the object for the user to know something wrong happened
        with self.pool.cursor() as cr:
            self.with_env(self.env(cr=cr)).write(vals)

    @api.multi
    def refresh_status(self, count=90, return_credentials=False):
        if count == 0:
            self.log_message(_('Timeout: Could not retrieve accounts informations'))
            raise UserError(_('Timeout: Could not retrieve accounts informations'))
        params = {'include': 'credentials'} if return_credentials else {}
        resp_json = self.yodlee_fetch('/providerAccounts/'+self.provider_account_identifier, params, {}, 'GET')
        refresh_info = resp_json.get('providerAccount', {}).get('refreshInfo')
        if return_credentials:
            self.write_status(refresh_info)
            return resp_json
        if refresh_info:
            status = refresh_info.get('status')
            if status == 'SUCCESS' or status == 'PARTIAL_SUCCESS':
                self.write_status(refresh_info)
                # if create_account:
                add_info = self.add_update_accounts()
                resp_json['numberAccountAdded'] = len(add_info['accounts_added'])
                resp_json['transactions'] = add_info['transactions']
                return resp_json
            elif status == 'IN_PROGRESS' and refresh_info.get('additionalStatus') == 'USER_INPUT_REQUIRED':
                # MFA process, check if we already have mfa information, if not continue to call service until we get mfa login form
                self.write_status(refresh_info)
                if not resp_json.get('providerAccount', {}).get('loginForm'):
                    time.sleep(2)
                    return self.refresh_status(count=count-1)
                else:
                    return resp_json
            elif status == 'IN_PROGRESS':
                time.sleep(2)
                return self.refresh_status(count=count-1)
            elif status == 'FAILED' and refresh_info.get('statusCode') == 0:
                # We are in a case where login has succeeded but there are different errors on different accounts
                self.add_update_accounts()
                message = ''
                for account in self.account_online_journal_ids:
                    if account.yodlee_status_code != 0:
                        message += self.get_error_from_code(account.yodlee_status_code) + '<br/>'
                if message == '':
                    message = 'The error might have happened on other accounts that are not in Odoo'
                self.log_message(message)
                raise UserError(_('Different error have occurred on different accounts, see provider account message for details'))
            elif status == 'FAILED':
                self.log_message(self.get_error_from_code(refresh_info.get('statusCode')))
                self.write_status(refresh_info)
                raise UserError(self.get_error_from_code(refresh_info.get('statusCode')))
            else:
                self.log_message(_('An error has occurred while trying to refresh accounts (type not supported)'))
                self.write_status(refresh_info)
                raise UserError(_('An error has occurred while trying to refresh accounts (type not supported)'))

    @api.multi
    def add_update_accounts(self):
        params = {'providerAccountId': self.provider_account_identifier}
        resp_json = self.yodlee_fetch('/accounts/', params, {}, 'GET')
        accounts = resp_json.get('account', [])
        accounts_added = self.env['account.online.journal']
        transactions = []
        for account in accounts:
            if account.get('CONTAINER') in ('bank', 'creditCard'):
                vals = {
                    'yodlee_account_status': account.get('accountStatus'),
                    'yodlee_status_code': account.get('refreshinfo', {}).get('statusCode'),
                    'balance': account.get('currentBalance', {}).get('amount', 0) if account.get('CONTAINER') == 'bank' else account.get('runningBalance', {}).get('amount', 0)
                }
                account_search = self.env['account.online.journal'].search([('account_online_provider_id', '=', self.id), ('online_identifier', '=', account.get('id'))], limit=1)
                if len(account_search) == 0:
                    dt = datetime.datetime
                    # Since we just create account, set last sync to 15 days in the past to retrieve transaction from latest 15 days
                    last_sync = dt.strftime(dt.strptime(self.last_refresh, DEFAULT_SERVER_DATETIME_FORMAT) - datetime.timedelta(days=15), DEFAULT_SERVER_DATE_FORMAT)
                    vals.update({
                        'name': account.get('accountName', 'Account'),
                        'online_identifier': account.get('id'),
                        'account_online_provider_id': self.id,
                        'account_number': account.get('accountNumber'),
                        'last_sync': last_sync,
                    })
                    with self.pool.cursor() as cr:
                        acc = self.with_env(self.env(cr=cr)).env['account.online.journal'].create(vals)
                    accounts_added += acc
                else:
                    with self.pool.cursor() as cr:
                        account_search.with_env(self.env(cr=cr)).env['account.online.journal'].write(vals)
                    # Also retrieve transaction if status is SUCCESS
                    if vals.get('yodlee_status_code') == 0 and account_search.journal_ids:
                        transactions_count = account_search.retrieve_transactions()
                        transactions.append({'journal': account_search.journal_ids[0].name, 'count': transactions_count})
        return {'accounts_added': accounts_added, 'transactions': transactions}

    @api.model
    def cron_fetch_online_transactions(self):
        if self.provider_type != 'yodlee':
            return super(YodleeProviderAccount, self).cron_fetch_online_transactions()
        self.refresh_status()

    @api.multi
    def unlink(self):
        for provider in self:
            if provider.provider_type == 'yodlee':
                # call yodlee to ask to remove link between user and provider_account_identifier
                try:
                    ctx = self._context.copy()
                    ctx['no_post_message'] = True
                    provider.with_context(ctx).yodlee_fetch('/providerAccounts/'+provider.provider_account_identifier, {}, {}, 'DELETE')
                except UserError:
                    # If call to yodlee fails, don't prevent user to delete record 
                    pass
        super(YodleeProviderAccount, self).unlink()

    def get_error_from_code(self, code):
        return {
            '409': _("Problem Updating Account(409): We could not update your account because the end site is experiencing technical difficulties."),
            '411': _("Site No Longer Available (411):The site no longer provides online services to its customers.  Please delete this account."),
            '412': _("Problem Updating Account(412): We could not update your account because the site is experiencing technical difficulties."),
            '415': _("Problem Updating Account(415): We could not update your account because the site is experiencing technical difficulties."),
            '416': _("Multiple User Logins(416): We attempted to update your account, but another session was already established at the same time.  If you are currently logged on to this account directly, please log off and try after some time"),
            '418': _("Problem Updating Account(418): We could not update your account because the site is experiencing technical difficulties. Please try later."),
            '423': _("No Account Found (423): We were unable to detect an account. Please verify that you account information is available at this time and If the problem persists, please contact customer support at online@odoo.com for further assistance."),
            '424': _("Site Down for Maintenance(424):We were unable to update your account as the site is temporarily down for maintenance. We apologize for the inconvenience.  This problem is typically resolved in a few hours. Please try later."),
            '425': _("Problem Updating Account(425): We could not update your account because the site is experiencing technical difficulties. Please try later."),
            '426': _("Problem Updating Account(426): We could not update your account for technical reasons. This type of error is usually resolved in a few days. We apologize for the inconvenience."),
            '505': _("Site Not Supported (505): We currently does not support the security system used by this site. We apologize for any inconvenience. Check back periodically if this situation has changed."),
            '510': _("Property Record Not Found (510): The site is unable to find any property information for your address. Please verify if the property address you have provided is correct."),
            '511': _("Home Value Not Found (511): The site is unable to provide home value for your property. We suggest you to delete this site."),
            '402': _("Credential Re-Verification Required (402): We could not update your account because your username and/or password were reported to be incorrect.  Please re-verify your username and password."),
            '405': _("Update Request Canceled(405):Your account was not updated because you canceled the request."),
            '406': _("Problem Updating Account (406): We could not update your account because the site requires you to perform some additional action. Please visit the site or contact its customer support to resolve this issue. Once done, please update your account credentials in case they are changed else try again."),
            '407': _("Account Locked (407): We could not update your account because it appears your account has been locked. This usually results from too many unsuccessful login attempts in a short period of time. Please visit the site or contact its customer support to resolve this issue.  Once done, please update your account credentials in case they are changed."),
            '414': _("Requested Account Type Not Found (414): We could not find your requested account. You may have selected a similar site under a different category by accident in which case you should select the correct site."),
            '417': _("Account Type Not Supported(417):The type of account we found is not currently supported.  Please remove this site and add as a  manual account."),
            '420': _("Credential Re-Verification Required (420):The site has merged with another. Please re-verify your credentials at the site and update the same."),
            '421': _("Invalid Language Setting (421): The language setting for your site account is not English. Please visit the site and change the language setting to English."),
            '422': _("Account Reported Closed (422): We were unable to update your account information because it appears one or more of your related accounts have been closed.  Please deactivate or delete the relevant account and try again."),
            '427': _("Re-verification Required (427): We could not update your account due to the site requiring you to view a new promotion. Please log in to the site and click through to your account overview page to update the account.  We apologize for the inconvenience."),
            '428': _("Re-verification Required (428): We could not update your account due to the site requiring you to accept a new Terms & Conditions. Please log in to the site and read and accept the T&C."),
            '429': _("Re-Verification Required (429): We could not update your account due to the site requiring you to verify your personal information. Please log in to the site and update the fields required."),
            '430': _("Site No Longer Supported (430):This site is no longer supported for data updates. Please deactivate or delete your account. We apologize for the inconvenience."),
            '433': _("Registration Requires Attention (433): Auto registration is not complete. Please complete your registration at the end site. Once completed, please complete adding this account."),
            '434': _("Registration Requires Attention (434): Your Auto-Registration could not be completed and requires further input from you.  Please re-verify your registration information to complete the process."),
            '435': _("Registration Requires Attention (435): Your Auto-Registration could not be completed and requires further input from you.  Please re-verify your registration information to complete the process."),
            '436': _("Account Already Registered (436):Your Auto-Registration could not be completed because the site reports that your account is already registered.  Please log in to the site to confirm and then complete the site addition process with the correct login information."),
            '506': _("New Login Information Required(506):We're sorry, to log in to this site, you need to provide additional information. Please update your account and try again."),
            '512': _("No Payees Found(512):Your request cannot be completed as no payees were found in your account."),
            '518': _("MFA error: Authentication Information Unavailable (518):Your account was not updated as the required additional authentication information was unavailable. Please try now."),
            '519': _("MFA error: Authentication Information Required (519): Your account was not updated as your authentication information like security question and answer was unavailable or incomplete. Please update your account settings."),
            '520': _("MFA error: Authentication Information Incorrect (520):We're sorry, the site indicates that the additional authentication information you provided is incorrect. Please try updating your account again."),
            '521': _("MFA error: Additional Authentication Enrollment Required (521) : Please enroll in the new security authentication system, <Account Name> has introduced. Ensure your account settings in <Cobrand> are updated with this information."),
            '522': _("MFA error: Request Timed Out (522) :Your request has timed out as the required security information was unavailable or was not provided within the expected time. Please try again."),
            '523': _("MFA error: Authentication Information Incorrect (523):We're sorry, the authentication information you  provided is incorrect. Please try again."),
            '524': _("MFA error: Authentication Information Expired (524):We're sorry, the authentication information you provided has expired. Please try again."),
            '526': _("MFA error: Credential Re-Verification Required (526): We could not update your account because your username/password or additional security credentials are incorrect. Please try again."),
            '401': _("Problem Updating Account(401):We're sorry, your request timed out. Please try again."),
            '403': _("Problem Updating Account(403):We're sorry, there was a technical problem updating your account. This kind of error is usually resolved in a few days. Please try again later."),
            '404': _("Problem Updating Account(404):We're sorry, there was a technical problem updating your account. Please try again later."),
            '408': _("Account Not Found(408): We're sorry, we couldn't find any accounts for you at the site. Please log in at the site and confirm that your account is set up, then try again."),
            '413': _("Problem Updating Account(413):We're sorry, we couldn't update your account at the site because of a technical issue. This type of problem is usually resolved in a few days. Please try again later."),
            '419': _("Problem Updating Account(419):We're sorry, we couldn't update your account because of unexpected variations at the site. This kind of problem is usually resolved in a few days. Please try again later."),
            '507': _("Problem Updating Account(507):We're sorry, Yodlee has just started providing data updates for this site, and it may take a few days to be successful as we get started. Please try again later."),
            '508': _("Request Timed Out (508): We are sorry, your request timed out due to technical reasons. Please try again."),
            '509': _("MFA error: Site Device Information Expired(509): We're sorry, we can't update your account because your token is no longer valid at the site. Please update your information and try again, or contact customer support."),
            '517': _("Problem Updating Account (517) :We'resorry, there was a technical problem updating your account. Please try again."),
            '525': _("MFA error: Problem Updating Account (525): We could not update your account for technical reasons. This type of error is usually resolved in a few days. We apologize for the inconvenience. Please try again later."),
        }.get(str(code), _('An Error has occurred (code %s)' % code))


class ResCompany(models.Model):
    _inherit = 'res.company'

    yodlee_access_token = fields.Char("access_token")
    yodlee_user_login = fields.Char("Yodlee login")
    yodlee_user_password = fields.Char("Yodlee password")
    yodlee_user_access_token = fields.Char("Yodlee access token")


class YodleeAccount(models.Model):
    _inherit = 'account.online.journal'
    '''
    The yodlee account that is saved in Odoo.
    It knows how to fetch Yodlee to get the new bank statements
    '''

    yodlee_account_status = fields.Char(help='Active/Inactive on Yodlee system', readonly=True)
    yodlee_status_code = fields.Integer(readonly=True)

    @api.multi
    def retrieve_transactions(self):
        if (self.account_online_provider_id.provider_type != 'yodlee'):
            return super(YodleeAccount, self).retrieve_transactions()
        if not self.journal_ids:
            return 0
        params = {
            'accountId': self.online_identifier,
            'fromDate': min(self.last_sync, self.account_online_provider_id.last_refresh[:10]),
            'toDate': fields.Date.today(),
        }

        resp_json = self.account_online_provider_id.yodlee_fetch('/transactions', params, {}, 'GET')
        transactions = []
        for tr in resp_json.get('transaction', []):
            # We only take posted transaction into account
            if tr.get('status') == 'POSTED':
                date = tr.get('date') or tr.get('postDate') or tr.get('transactionDate')
                dt = datetime.datetime
                date = dt.strftime(dt.strptime(date, '%Y-%m-%d'), DEFAULT_SERVER_DATE_FORMAT)
                amount = tr.get('amount', {}).get('amount')
                # ignore transaction with 0
                if amount == 0:
                    continue
                transactions.append({
                    'id': str(tr.get('id'))+':'+tr.get('CONTAINER'),
                    'date': date,
                    'description': tr.get('description',{}).get('original', 'No description'),
                    'amount': amount * -1 if tr.get('baseType') == 'DEBIT' else amount,
                    'end_amount': self.balance,
                    })
        return self.env['account.bank.statement'].online_sync_bank_statement(transactions, self.journal_ids[0])
