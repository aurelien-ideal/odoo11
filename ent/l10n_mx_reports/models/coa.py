# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _, fields, tools
from openerp.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.xml_utils import _check_with_xsd

MX_NS_REFACTORING = {
    'catalogocuentas__': 'catalogocuentas',
    'BCE__': 'BCE',
}

CFDICOA_TEMPLATE = 'l10n_mx_reports.cfdi11coa'
CFDICOA_XSD = 'l10n_mx_reports/data/xsd/%s/cfdi11coa.xsd'
CFDICOA_XSLT_CADENA = 'l10n_mx_reports/data/xslt/%s/CatalogoCuentas_1_1.xslt'


class MXReportAccountCoa(models.AbstractModel):
    _name = "l10n_mx.coa.report"
    _inherit = "l10n_mx.trial.report"
    _description = "Mexican Chart of Account Report"

    filter_date = None
    filter_comparison = None
    filter_cash_basis = None
    filter_all_entries = None
    filter_hierarchy = None
    filter_journals = None

    def get_templates(self):
        templates = super(MXReportAccountCoa, self).get_templates()
        #use the main template instead of the trial balance with 2 header lines
        templates['main_template'] = 'account_reports.main_template'
        return templates

    def get_columns_name(self, options):
        return [{'name': ''}, {'name': _('Nature')}]

    def get_lines(self, options, line_id=None):
        options['coa_only'] = True
        lines = self._post_process({}, {}, options, [])
        if lines:
            afrl_obj = self.env['account.financial.html.report.line']
            afr_lines = afrl_obj.search([
                ('parent_id', '=', False),
                ('code', 'ilike', 'MX_COA_%')], order='code')
            lines.extend(self._get_accounts_not_found(afr_lines))
        return lines

    def _get_accounts_not_found(self, afr_lines):
        """Add the accounts that are not found with domains in the AFR
        lines, with this the is indicated the accounts that will not show in
        the report."""
        accounts = []
        lines = []
        account_obj = self.env['account.account']
        for domain in afr_lines.mapped('children_ids').mapped('domain'):
            account_ids = account_obj.search(
                safe_eval(domain or '[]'), order='code')
            accounts.extend(account_ids.ids)
        accounts = account_obj.search([
            ('id', 'not in', list(set(accounts))),
            ('deprecated', '=', False)])

        if accounts:
            lines.append({
                'id': 'misconfigured_accounts',
                'type': 'line',
                'name': _('Misconfigured Accounts'),
                'footnotes': {},
                'columns': [{'name': ''}],
                'level': 1,
                'unfoldable': False,
                'unfolded': True,
            })
            for account in accounts:
                name = '%s %s' % (account.code, account.name)
                name = name[:133] + "..." if len(name) > 135 else name
                lines.append({
                    'id': account.id,
                    'type': 'account_id',
                    'name': name,
                    'footnotes': {},
                    'columns': [{'name': ''}],
                    'level': 3,
                    'caret_options': 'account.account',
                    'unfoldable': False,
                    'unfolded': True,
                })
        return lines

    def get_coa_dict(self, options):
        xml_data = self.get_lines(options)
        accounts = []
        account_lines = [l for l in xml_data
                         if l.get('caret_options') == 'account.account']
        account_obj = self.env['account.account']
        for line in account_lines:
            account = account_obj.browse(line['id'])
            tag = account.tag_ids.filtered(lambda r: r.color == 4)
            if not tag:
                msg = _(
                    'This XML could not be generated because some accounts '
                    'are not correctly configured and can not be added in '
                    'this report. This accounts are found in the section '
                    '"Misconfigured Accounts", please configure your tag and '
                    'try generate the report XML again.')
                raise ValidationError(msg)
            accounts.append({
                'code': tag.name[:6],
                'number': account.code,
                'name': account.name,
                'level': '2',
                'nature': tag.nature,
            })
        chart = {
            'vat': self.env.user.company_id.vat or '',
            'month': str(fields.date.today().month).zfill(2),
            'year': fields.date.today().year,
            'accounts': accounts
        }
        return chart

    def get_xml(self, options):
        qweb = self.env['ir.qweb']
        version = '1.1'
        values = self.get_coa_dict(options)
        cfdicoa = qweb.render(CFDICOA_TEMPLATE, values=values)
        for key, value in MX_NS_REFACTORING.items():
            cfdicoa = cfdicoa.replace(key.encode('UTF-8'),
                                      value.encode('UTF-8') + b':')

        with tools.file_open(CFDICOA_XSD % version, "rb") as xsd:
            _check_with_xsd(cfdicoa, xsd)
        return cfdicoa

    def get_report_name(self):
        """The structure to name the CoA reports is:
        VAT + YEAR + MONTH + CT"""
        return '%s%s%sCT' % (
            self.env.user.company_id.vat or '',
            fields.date.today().year,
            str(fields.date.today().month).zfill(2))
