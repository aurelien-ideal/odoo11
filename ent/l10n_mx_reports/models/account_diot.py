# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from __future__ import division

from datetime import datetime, timedelta

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, float_compare


class MxReportPartnerLedger(models.AbstractModel):
    _name = "l10n_mx.account.diot"
    _inherit = "account.report"
    _description = "DIOT"

    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_month'}
    filter_all_entries = False

    def get_columns_name(self, options):
        return [
            {},
            {'name': _('Type of Operation')},
            {'name': _('Type of Third')},
            {'name': _('VAT')},
            {'name': _('Country')},
            {'name': _('Nationality')},
            {'name': _('Paid 16%'), 'class': 'number'},
            {'name': _('Importation 16%'), 'class': 'number'},
            {'name': _('Paid 0%'), 'class': 'number'},
            {'name': _('Exempt'), 'class': 'number'},
            {'name': _('Withheld'), 'class': 'number'}
        ]

    def do_query(self, options, line_id):
        select = ',\"account_move_line_account_tax_rel\".account_tax_id, SUM(\"account_move_line\".debit - \"account_move_line\".credit)'  # noqa
        if options.get('cash_basis'):
            select = select.replace('debit', 'debit_cash_basis').replace(
                'credit', 'credit_cash_basis')
        sql = "SELECT \"account_move_line\".partner_id%s FROM %s WHERE %s%s AND \"account_move_line_account_tax_rel\".account_move_line_id = \"account_move_line\".id GROUP BY \"account_move_line\".partner_id, \"account_move_line_account_tax_rel\".account_tax_id"  # noqa
        context = self.env.context
        journal_ids = []
        for company in self.env['res.company'].browse(context[
                'company_ids']).filtered('tax_cash_basis_journal_id'):
            journal_ids.append(company.tax_cash_basis_journal_id.id)
        tax_ids = self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('tax_exigibility', '=', 'on_payment')])
        account_tax_ids = tax_ids.mapped('cash_basis_account')
        domain = [
            ('journal_id', 'in', journal_ids),
            ('account_id', 'not in', account_tax_ids.ids),
            ('tax_ids', 'in', tax_ids.ids),
        ]
        tables, where_clause, where_params = self.env[
            'account.move.line']._query_get(domain)
        tables += ',"account_move_line_account_tax_rel"'
        line_clause = line_id and\
            ' AND \"account_move_line\".partner_id = ' + str(line_id) or ''
        query = sql % (select, tables, where_clause, line_clause)
        self.env.cr.execute(query, where_params)
        results = self.env.cr.fetchall()
        result = {}
        for res in results:
            result.setdefault(res[0], {}).setdefault(res[1], res[2])
        return result

    def group_by_partner_id(self, options, line_id):
        partners = {}
        results = self.do_query(options, line_id)
        mx_country = self.env.ref('base.mx')
        initial_bal_date_to = datetime.strptime(self.env.context[
            'date_from_aml'], DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=-1)
        initial_bal_results = self.with_context(
            date_to=initial_bal_date_to.strftime(
                DEFAULT_SERVER_DATE_FORMAT)).do_query(options, line_id)
        context = self.env.context
        journal_ids = []
        for company in self.env['res.company'].browse(
                context['company_ids']).filtered('tax_cash_basis_journal_id'):
            journal_ids.append(company.tax_cash_basis_journal_id.id)
        tax_ids = self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('tax_exigibility', '=', 'on_payment')])
        account_tax_ids = tax_ids.mapped('cash_basis_account')
        base_domain = [
            ('date', '<=', context['date_to']),
            ('company_id', 'in', context['company_ids']),
            ('journal_id', 'in', journal_ids),
            ('account_id', 'not in', account_tax_ids.ids),
            ('tax_ids', '!=', False),
        ]
        if context['date_from_aml']:
            base_domain.append(('date', '>=', context['date_from_aml']))
        if context['state'] == 'posted':
            base_domain.append(('move_id.state', '=', 'posted'))
        without_vat = []
        without_too = []
        for partner_id, result in results.items():
            domain = list(base_domain)  # copying the base domain
            domain.append(('partner_id', '=', partner_id))
            partner = self.env['res.partner'].browse(partner_id)
            partners[partner] = result
            partners[partner]['initial_bal'] = initial_bal_results.get(
                partner.id, {'balance': 0, 'debit': 0, 'credit': 0})
            if not context.get('print_mode'):
                #  fetch the 81 first amls. The report only displays the first
                # 80 amls. We will use the 81st to know if there are more than
                # 80 in which case a link to the list view must be displayed.
                partners[partner]['lines'] = self.env[
                    'account.move.line'].search(domain, order='date', limit=81)
            else:
                partners[partner]['lines'] = self.env[
                    'account.move.line'].search(domain, order='date')
            without_vat += (
                (partner.name,)
                if partner.country_id == mx_country and not partner.vat and
                partners[partner]['lines']
                else ())
            without_too += ((partner.name,)
                            if not partner.l10n_mx_type_of_operation and
                            partners[partner]['lines']
                            else ())
        if (without_vat or without_too) and self._context.get('raise'):
            msg = _('The report cannot be generated because of: ')
            msg += (
                _('\n\nThe following partners do not have a '
                  'valid RFC: \n - %s') %
                '\n - '.join(without_vat) if without_vat else '')
            msg += (
                _('\n\nThe following partners do not have a '
                  'type of operation: \n - %s') %
                '\n - '.join(without_too) if without_too else '')
            msg += _(
                '\n\nPlease fill the missing information in the partners and '
                'try again.')

            raise UserError(msg)

        return partners

    @api.model
    def get_lines(self, options, line_id=None):
        lines = []
        if line_id:
            line_id = line_id.replace('partner_', '')
        context = self.env.context
        company_id = context.get('company_id') or self.env.user.company_id
        grouped_partners = self.with_context(
            date_from_aml=context['date_from'], date_from=context[
                'date_from'] and company_id.compute_fiscalyear_dates(
                    datetime.strptime(
                        context['date_from'], DEFAULT_SERVER_DATE_FORMAT))[
                            'date_from'] or None).group_by_partner_id(options, line_id)
        # Aml go back to the beginning of the user chosen range but the
        # amount on the partner line should go back to either the beginning of
        # the fy or the beginning of times depending on the partner
        sorted_partners = sorted(grouped_partners, key=lambda p: p.name or '')
        unfold_all = context.get('print_mode') and not options.get('unfolded_lines')
        tag_16 = self.env.ref('l10n_mx.tag_diot_16')
        tag_0 = self.env.ref('l10n_mx.tag_diot_0')
        tag_ret = self.env.ref('l10n_mx.tag_diot_ret')
        tag_exe = self.env.ref('l10n_mx.tag_diot_exento')
        tax_ids = self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase')])
        tax16 = tax_ids.search([('id', 'in', tax_ids.ids),
                                ('tag_ids', 'in', tag_16.ids)])
        tax0 = tax_ids.search([('id', 'in', tax_ids.ids),
                               ('tag_ids', 'in', tag_0.ids)])
        tax_ret = tax_ids.search([('id', 'in', tax_ids.ids),
                                  ('tag_ids', 'in', tag_ret.ids)])
        tax_exe = tax_ids.search([('id', 'in', tax_ids.ids),
                                  ('tag_ids', 'in', tag_exe.ids)])
        for partner in sorted_partners:
            amls = grouped_partners[partner]['lines']
            if not amls:
                continue
            if not partner:
                for line in amls:
                    lines.append({
                        'id': str(line.id),
                        'name': '',
                        'columns': [{'name': ''}],
                        'level': 1,
                        'colspan': 10
                    })
                continue
            p_columns = [
                partner.l10n_mx_type_of_third or '', partner.l10n_mx_type_of_operation or '',
                partner.vat or '', partner.country_id.code or '',
                partner.l10n_mx_nationality or '']
            partner_data = grouped_partners[partner]
            total_tax16 = 0
            total_tax0 = 0
            exempt = 0
            withh = 0
            for tax in tax16.ids:
                total_tax16 += partner_data.get(tax, 0)
            p_columns.append(int(round(total_tax16, 0)))
            p_columns.append(0)
            total_tax0 += sum([partner_data.get(tax, 0) for tax in tax0.ids])
            p_columns.append(int(round(total_tax0, 0)))
            exempt += sum([partner_data.get(exem, 0)
                           for exem in tax_exe.ids])
            p_columns.append(int(round(exempt, 0)))
            withh += sum([abs(partner_data.get(ret.id, 0) / (100 / ret.amount))
                          for ret in tax_ret])
            p_columns.append(int(round(withh, 0)))
            unfolded = 'partner_' + str(partner.id) in options.get('unfolded_lines') or unfold_all
            lines.append({
                'id': 'partner_' + str(partner.id),
                'name': partner.name,
                'columns': [{'name': v} for v in p_columns],
                'level': 2,
                'unfoldable': True,
                'unfolded': unfolded,
            })
            if not (unfolded):
                continue
            progress = 0
            domain_lines = []
            amls = grouped_partners[partner]['lines']
            too_many = False
            if len(amls) > 80 and not context.get('print_mode'):
                amls = amls[-80:]
                too_many = True
            for line in amls:
                if options['cash_basis']:
                    line_debit = line.debit_cash_basis
                    line_credit = line.credit_cash_basis
                else:
                    line_debit = line.debit
                    line_credit = line.credit
                progress = progress + line_debit - line_credit
                name = line.display_name
                name = name[:32] + "..." if len(name) > 35 else name
                columns = ['', '', '', '']
                columns.append('')
                total_tax16 = 0
                total_tax0 = 0
                exempt = 0
                withh = 0
                total_tax16 += sum([
                    line.debit or line.credit * -1
                    for tax in tax16.ids if tax in line.tax_ids.ids])
                columns.append(int(round(total_tax16, 0)))
                columns.append(0)
                total_tax0 += sum([
                    line.debit or line.credit * -1
                    for tax in tax0.ids if tax in line.tax_ids.ids])
                columns.append(int(round(total_tax0, 0)))
                exempt += sum([line.debit or line.credit * -1
                               for exem in tax_exe.ids
                               if exem in line.tax_ids.ids])
                columns.append(int(round(exempt, 0)))
                withh += sum([
                    abs((line.debit or line.credit * -1) / (100 / ret.amount))
                    for ret in tax_ret
                    if ret.id in line.tax_ids.ids])
                columns.append(int(round(withh, 0)))
                caret_type = 'account.move'
                if line.invoice_id:
                    caret_type = 'account.invoice.in' if line.invoice_id.type in ('in_refund', 'in_invoice') else 'account.invoice.out'
                elif line.payment_id:
                    caret_type = 'account.payment'
                domain_lines.append({
                    'id': str(line.id),
                    'parent_id': 'partner_' + str(partner.id),
                    'name': name,
                    'columns': [{'name':v} for v in columns],
                    'caret_options': caret_type,
                    'level': 1,
                })
            domain_lines.append({
                'id': 'total_' + str(partner.id),
                'parent_id': 'partner_' + str(partner.id),
                'class': 'o_account_reports_domain_total',
                'name': _('Total') + ' ' + partner.name,
                'columns': [{'name': v} for v in p_columns],
                'level': 1,
            })
            if too_many:
                domain_lines.append({
                    'id': 'too_many_' + str(partner.id),
                    'parent_id': 'partner_' + str(partner.id),
                    'name': _('There are more than 80 items in this list, '
                              'click here to see all of them'),
                    'colspan': 10,
                    'columns': [{}],
                    'level': 3,
                })
            lines += domain_lines
        return lines

    @api.model
    def get_report_name(self):
        return _('DIOT')

    def get_reports_buttons(self):
        buttons = super(MxReportPartnerLedger, self).get_reports_buttons()
        buttons += [{'name': _('Print DIOT (TXT)'), 'action': 'print_txt'}]
        return buttons

    def get_txt(self, options):
        ctx = self.set_context(options)
        ctx.update({'no_format':True, 'print_mode':True, 'raise': True})
        #data_check = self.with_context(ctx).check_data_report(options)
        #if data_check.get('name', ''):
        #    raise ValidationError(data_check.get('name', ''))
        return self.with_context(ctx)._l10n_mx_diot_txt_export(options)

    #@api.model
    #def check_data_report(self, options):
    #    data = self.get_lines(options)
    #    lines_wo_partner = self.check_lines_wo_partner(
    #        [l for l in data if l.get('type', False) == 'line_wo_partner'])
    #    partner_wo_data = self.check_lines_partner_data(
    #        [l for l in data if l.get('type', False) == 'line'])
    #    moves_0 = self.check_lines_amount(
    #        [l for l in data if l.get('type', False) == 'move_line_id'])
    #    return lines_wo_partner or partner_wo_data or moves_0

    #@api.multi
    #def check_lines_wo_partner(self, lines):
    #    moves_wo_partner = []
    #    moves_wo_partner.extend([
    #        line['id'] for line in lines if line.get('id')])
    #    if not moves_wo_partner:
    #        return {}
    #    return {
    #        'type': 'ir.actions.act_window',
    #        'name': _('Moves without supplier'),
    #        'res_model': 'account.move.line',
    #        'views': [[False, 'list'], [False, 'form']],
    #        'domain': [['id', 'in', moves_wo_partner]],
    #    }

    #@api.multi
    #def check_lines_partner_data(self, lines):
    #    partners = []
    #    partners.extend([int(line['id']) for line in lines if line.get('id')])
    #    partners = self.env['res.partner'].browse(
    #        partners)._get_not_partners_diot()
    #    if not partners:
    #        return {}
    #    return {
    #        'type': 'ir.actions.act_window',
    #        'name': _('Suppliers without information necessary for DIOT'),
    #        'res_model': 'res.partner',
    #        'views': [[False, 'list'], [False, 'form']],
    #        'domain': [
    #            ['id', 'in', partners.ids], ['active', 'in', [True, False]]],
    #    }

    #@api.multi
    #def check_lines_amount(self, lines):
    #    moves0 = [line['id'] for line in lines
    #              if line.get('id') and not sum(line.get('columns', [])[5:])]
    #    if not moves0:
    #        return {}
    #    return {
    #        'type': 'ir.actions.act_window',
    #        'name': _('Movements to corroborate the amounts of taxes'),
    #        'res_model': 'account.move.line',
    #        'views': [[False, 'list'], [False, 'form']],
    #        'domain': [['id', 'in', moves0]],
    #    }

    def _l10n_mx_diot_txt_export(self, options):
        txt_data = self.get_lines(options)
        lines = ''
        for line in txt_data:
            if not line.get('id').startswith('partner_'):
                continue
            columns = line.get('columns', [])
            if not sum([c.get('name', 0) for c in columns[5:]]):
                continue
            data = [''] * 23
            data[0] = columns[0]['name']
            data[1] = columns[1]['name']
            data[2] = columns[2]['name'] if columns[0]['name'] == '04' else ''
            data[3] = columns[2]['name'] if columns[0]['name'] != '04' else ''
            data[4] = u''.join(line.get('name', '')).encode('utf-8').strip()
            data[5] = columns[3]['name']
            data[6] = u''.join(columns[4]['name']).encode('utf-8').strip()
            data[7] = int(columns[5]['name']) if columns[5]['name'] else ''
            data[13] = int(columns[6]['name']) if columns[6]['name'] else ''
            data[18] = int(columns[7]['name']) if columns[7]['name'] else ''
            data[19] = int(columns[8]['name']) if columns[8]['name'] else ''
            data[20] = int(columns[9]['name']) if columns[9]['name'] else ''
            lines += '|'.join(str(d) for d in data) + '\n'
        return lines
