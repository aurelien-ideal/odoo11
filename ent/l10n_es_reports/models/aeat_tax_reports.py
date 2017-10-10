# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.addons.account_reports.models.account_financial_report import FormulaLine


class AEATAccountFinancialReport(models.Model):
    _inherit = 'account.financial.html.report'

    CASILLA_FIELD_PREFIX = 'casilla_'

    def get_lines(self, options, line_id=None):
        """ Overridden in order to add the 'financial_report_line_values' attribute
        to the context before calling super() in case some AEAT wizard was used
        to generate this report. This allows transmitting the values manually
        entered in the wizard to the report lines.
        """
        context_line_values = {}

        aeat_wizard_id = self.env.context.get('aeat_wizard_id')
        aeat_modelo = self.env.context.get('aeat_modelo')
        if aeat_wizard_id and aeat_modelo: # If we do have these, it means an AEAT wizard was used to generate this report
            aeat_wizard = self.env['l10n_es_reports.mod' + aeat_modelo + '.wizard'].browse(aeat_wizard_id)
            casilla_prefix = self.CASILLA_FIELD_PREFIX

            # We consider all the casilla fields from the wizard, as they each correspond to a report line.
            casilla_fields = [x for x in dir(aeat_wizard) if x.startswith(casilla_prefix)]
            for attr in casilla_fields:
                line_code = 'aeat_mod_' + aeat_wizard._modelo + '_' + attr.replace(self.CASILLA_FIELD_PREFIX, '')
                context_line_values[line_code] = getattr(aeat_wizard, attr)

        return super(AEATAccountFinancialReport, self.with_context(self.env.context, financial_report_line_values=context_line_values)).get_lines(options, line_id)
