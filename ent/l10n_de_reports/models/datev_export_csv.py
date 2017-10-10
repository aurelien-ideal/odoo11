# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT

from datetime import datetime
import json

class AccountMoveL10NDe(models.Model):
    _inherit = 'account.move'

    l10n_de_datev_main_account_id = fields.Many2one('account.account', compute='_get_datev_account',
        help='Technical field needed for datev export', store=True)

    @api.depends('journal_id', 'line_ids', 'journal_id.default_debit_account_id', 'journal_id.default_credit_account_id')
    def _get_datev_account(self):
        for move in self:
            value = False
            # If move has an invoice, return invoice's account_id
            invoice = self.env['account.invoice'].search([('move_id', '=', move.id)])
            if len(invoice):
                move.l10n_de_datev_main_account_id = invoice[0].account_id
                continue
            # If move belongs to a bank journal, return the journal's account (debit/credit should normally be the same)
            if move.journal_id == 'bank' and move.journal_id.default_debit_account_id:
                move.l10n_de_datev_main_account_id = move.journal_id.default_debit_account_id
                continue
            # If the move is an automatic exchange rate entry, take the gain/loss account set on the exchange journal
            elif move.journal_id == 'general' and move.journal_id == self.env.user.company_id.currency_exchange_journal_id:
                accounts = [
                    move.journal_id.default_debit_account_id,
                    move.journal_id.default_credit_account_id,
                ]
                lines = move.line_ids.filtered(lambda r: r.account_id in accounts)
                if len(lines) == 1:
                    move.l10n_de_datev_main_account_id = lines.account_id
                    continue

            # Look for an account used a single time in the move, that has no originator tax
            aml_debit = self.env['account.move.line']
            aml_credit = self.env['account.move.line']
            for aml in move.line_ids:
                if aml.debit > 0:
                    aml_debit += aml
                if aml.credit > 0:
                    aml_credit += aml
            if len(aml_debit) == 1:
                value = aml_debit[0].account_id
            elif len(aml_credit) == 1:
                value = aml_credit[0].account_id
            else:
                aml_debit_wo_tax = [a for a in aml_debit if not a.tax_line_id]
                aml_credit_wo_tax = [a for a in aml_credit if not a.tax_line_id]
                if len(aml_debit_wo_tax) == 1:
                    value = aml_debit_wo_tax[0].account_id
                elif len(aml_credit_wo_tax) == 1:
                    value = aml_credit_wo_tax[0].account_id
            move.l10n_de_datev_main_account_id = value


class DatevExportCSV(models.AbstractModel):
    _inherit = 'account.general.ledger'

    def get_reports_buttons(self):
        buttons = super(DatevExportCSV, self).get_reports_buttons()
        buttons += [{'name': _('Export Datev (csv)'), 'action': 'print_csv'}]
        return buttons

    def print_csv(self, options):
        return {
                'type': 'ir_actions_account_report_download',
                'data': {'model': self.env.context.get('model'),
                         'options': json.dumps(options),
                         'output_format': 'csv',
                         }
                }

    # Source: http://www.datev.de/dnlexom/client/app/index.html#/document/1036228/D103622800029
    def get_csv(self, options):
        header = u'"Währungskennung";"Soll-/Haben-Kennzeichen";"Umsatz (ohne Soll-/Haben-Kennzeichen)";"BU-Schlüssel";"Gegenkonto (ohne BU-Schlüssel)";"Belegfeld 1";"Belegfeld 2";"Datum";"Konto";"EU-Land und UStID";"Kurs"'

        move_line_ids = self.with_context(self.set_context(options), print_mode=True, aml_only=True).get_lines(options)
        lines = [header]
        for aml in self.env['account.move.line'].browse(move_line_ids):
            if aml.debit == aml.credit:
                # Ignore debit = credit = 0
                continue
            #account and counterpart account
            account_code = aml.move_id.l10n_de_datev_main_account_id.code[:4]
            to_account_code = u'{code}'.format(code=aml.account_id.code)[:4]

            #reference
            receipt1 = aml.move_id.name[:12]
            if aml.move_id.journal_id.type == 'purchase' and aml.move_id.ref:
                receipt1 = aml.move_id.ref[:12]

            #on receivable/payable aml of sales/purchases
            receipt2 = ''
            if to_account_code == account_code and aml.date_maturity:
                receipt2 = datetime.strptime(aml.date, DEFAULT_SERVER_DATE_FORMAT).strftime('%d%m%y')

            currency = aml.company_id.currency_id
            partner_vat = aml.tax_line_id and aml.move_id.partner_id.vat or ''
            code_correction = aml.tax_line_id and aml.tax_line_id.l10n_de_datev_code or ''
            line_value = {
                'waehrung': currency.name,
                'sollhaben': 's' if aml.balance <= 0 else 'h',
                'umsatz': str(abs(aml.balance)).replace('.', ','),
                'buschluessel': code_correction,
                'gegenkonto': to_account_code,
                'belegfeld1': receipt1,
                'belegfeld2': receipt2,
                'datum': datetime.strptime(aml.move_id.date, DEFAULT_SERVER_DATE_FORMAT).strftime('%d%m'),
                'konto': account_code or '',
                'eulandUSTID': partner_vat,
                'kurs': str(currency.rate).replace('.', ','),
            }
            lines.append(u'"{waehrung}";"{sollhaben}";"{umsatz}";"{buschluessel}";"{gegenkonto}";"{belegfeld1}";"{belegfeld2}";"{datum}";"{konto}";"{eulandUSTID}";"{kurs}"'.format(**line_value))
        return u'\n'.join(lines).encode('iso-8859-1') + b'\n'
