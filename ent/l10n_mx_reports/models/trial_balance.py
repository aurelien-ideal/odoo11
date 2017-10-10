# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, fields, tools
from odoo.tools.safe_eval import safe_eval
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

MX_NS_REFACTORING = {
    'catalogocuentas__': 'catalogocuentas',
    'BCE__': 'BCE',
}

CFDIBCE_TEMPLATE = 'l10n_mx_reports.cfdi11balance'
CFDIBCE_XSD = 'l10n_mx_reports/data/xsd/%s/cfdi11balance.xsd'
CFDIBCE_XSLT_CADENA = ('l10n_mx_reports/data/xslt/%s'
                       '/BalanzaComprobacion_1_1.xslt')


# TODO: When the module l10n_mx_edi is merged use the method in that module
def create_list_html(array):
    '''Create a html list of error for the chatter.
    '''
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'


class MxReportAccountTrial(models.AbstractModel):
    _name = "l10n_mx.trial.report"
    _inherit = "account.coa.report"
    _description = "Mexican Trial Balance Report"

    filter_hierarchy = None

    def get_reports_buttons(self):
        """Create the buttons to be used to download the required files"""
        buttons = super(MxReportAccountTrial, self).get_reports_buttons()
        buttons += [{'name': _('Export For SAT (XML)'), 'action': 'print_xml'}]
        return buttons

    def _post_process(self, grouped_accounts, initial_balances, options, comparison_table):
        if self.env.user.company_id.country_id.code.upper() == 'MX':
            # TODO: something like: and all([c.country_id.code == 'MX' for c in options.companies]):
            afrl_obj = self.env['account.financial.html.report.line']

            lines = []
            afr_lines = afrl_obj.search([
                ('parent_id', '=', False),
                ('code', 'ilike', 'MX_COA_%')], order='code')
            for line in afr_lines:
                childs = self._get_lines_second_level(
                    line.children_ids, grouped_accounts, initial_balances, options, comparison_table)
                if not childs:
                    continue
                cols = ['']
                if not options.get('coa_only'):
                    cols += ['' for p in range(len(comparison_table))] * 2 + ['']
                lines.append({
                    'id': 'hierarchy_' + line.code,
                    'name': line.name,
                    'columns': [{'name': v} for v in cols],
                    'level': 1,
                    'unfoldable': False,
                    'unfolded': True,
                })
                lines.extend(childs)
            return lines
        return super(MxReportAccountTrial, self)._post_process(grouped_accounts, initial_balances, options, comparison_table)

    @api.model
    def _get_lines_second_level(self, lines_child, grouped_accounts,
                                initial_balances, options, comparison_table):
        """Return list of tags found in the second level"""
        lines = []
        sorted_childs = sorted(lines_child, key=lambda a: a.name)
        for child in sorted_childs:
            account_lines = self._get_lines_third_level(
                child, grouped_accounts, initial_balances, options,
                comparison_table)
            if not account_lines:
                continue
            cols = ['']
            if not options.get('coa_only'):
                cols += ['' for p in range(len(comparison_table))] * 2 + ['']
            lines.append({
                'id': 'hierarchy_' + child.code,
                'name': child.name,
                'columns': [{'name': v} for v in cols],
                'level': 2,
                'unfoldable': False,
                'unfolded': True,
            })
            lines.extend(account_lines)
        return lines

    @api.model
    def _get_lines_third_level(self, line, grouped_accounts, initial_balances,
                               options, comparison_table):
        """Return list of accounts found in the third level"""
        lines = []
        context = self.env.context
        company_id = context.get('company_id') or self.env.user.company_id
        is_zero = company_id.currency_id.is_zero
        domain = safe_eval(line.domain or '[]')
        domain.append((('deprecated', '=', False)))
        account_ids = self.env['account.account'].search(domain, order='code')
        for account in account_ids:
            #skip accounts with all periods = 0 and no initial balance
            non_zero = False
            for period in range(len(comparison_table)):
                if account in grouped_accounts and (
                  not is_zero(grouped_accounts[account][period]['balance']) or not is_zero(initial_balances.get(account, 0))):
                    non_zero = True
            if not non_zero and not options.get('coa_only'):
                continue
            name = account.code + " " + account.name
            name = name[:98] + "..." if len(name) > 100 else name
            tag = account.tag_ids.filtered(lambda r: r.color == 4)
            nature = dict(tag.fields_get()['nature']['selection']).get(tag.nature, '')
            cols = [nature]
            if not options.get('coa_only'):
                cols = [self.format_value(initial_balances.get(account, 0.0))]
                total_periods = 0
                for period in range(len(comparison_table)):
                    amount = grouped_accounts[account][period]['balance']
                    total_periods += amount
                    cols += [self.format_value(grouped_accounts[account][period]['debit']),
                             self.format_value(grouped_accounts[account][period]['credit'])]
                cols += [self.format_value(initial_balances.get(account, 0.0) + total_periods)]
            lines.append({
                'id': account.id,
                'parent_id': 'hierarchy_' + line.code,
                'name': name,
                'columns': [{'name': v} for v in cols],
                'unfoldable': False,
                'caret_options': 'account.account',
            })
        return lines

    def get_bce_dict(self, options):
        company = self.env.user.company_id
        xml_data = self.get_lines(options)
        accounts = []
        account_obj = self.env['account.account']
        account_lines = [l for l in xml_data
                         if l.get('caret_options') == 'account.account' and
                         l.get('show', True)]
        for line in account_lines:
            account = account_obj.browse(line['id'])
            tag = account.tag_ids.filtered(lambda r: r.color == 4)
            if not tag:
                continue
            cols = line.get('columns', [])
            initial, debit, credit, end = (
                cols[0].get('name') or 0.0,
                cols[-3].get('name') or 0.0,
                cols[-2].get('name') or 0.0,
                cols[-1].get('name') or 0.0)
            accounts.append({
                'number': account.code,
                'initial': str(initial),
                'debit': str(debit),
                'credit': str(credit),
                'end': str(end),
            })
        date = fields.datetime.strptime(
            self.env.context['date_from'], DEFAULT_SERVER_DATE_FORMAT)
        chart = {
            'vat': company.vat or '',
            'month': str(date.month).zfill(2),
            'year': date.year,
            'accounts': accounts,
            'type': 'N',
        }
        return chart

    @api.model
    def get_xml(self, options):
        qweb = self.env['ir.qweb']
        version = '1.1'
        ctx = self.set_context(options)
        if not ctx.get('date_to'):
            return False
        ctx['no_format'] = True
        values = self.with_context(ctx).get_bce_dict(options)
        cfdicoa = qweb.render(CFDIBCE_TEMPLATE, values=values)
        for key, value in MX_NS_REFACTORING.items():
            cfdicoa = cfdicoa.replace(key.encode('UTF-8'),
                                      value.encode('UTF-8') + b':')

        with tools.file_open(CFDIBCE_XSD % version, "rb") as xsd:
            _check_with_xsd(cfdicoa, xsd)
        return cfdicoa

    def get_report_name(self):
        """The structure to name the Trial Balance reports is:
        VAT + YEAR + MONTH + ReportCode
        ReportCode:
        BN - Trial balance with normal information
        BC - Trial balance with with complementary information. (Now is
        not suportes)"""
        return '%s%s%sBN' % (
            self.env.user.company_id.vat or '',
            fields.date.today().year,
            str(fields.date.today().month).zfill(2))
