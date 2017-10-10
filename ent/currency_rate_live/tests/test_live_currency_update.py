import unittest
from odoo.tests.common import TransactionCase


class CurrencyTestCase(TransactionCase):

    @unittest.skip("Currency rate live test disabled as it requires to contact external servers")
    def test_live_currency_update(self):
        company_ecb = self.env['res.company'].create({'name': 'TEST ECB', 'currency_provider': 'ecb'})
        company_yah = self.env['res.company'].create({'name': 'TEST YAH', 'currency_provider': 'yahoo'})
        company_fta = self.env['res.company'].create({'name': 'TEST FTA', 'currency_provider': 'fta'})
        company_banxico = self.env['res.company'].create({'name': 'TEST BANXICO', 'currency_provider': 'banxico'})
        # testing Swiss Federal Tax Administration requires that Franc Suisse can be found
        # which is not the case in runbot/demo data as l10n_ch is not always installed
        self.env.ref('base.CHF').write({'active': True})

        #check the number of rates for USD
        self.currency_usd = self.env.ref('base.USD')
        rates_number = len(self.currency_usd.rate_ids)

        #get the live rate for all companies, each one with a different method
        res_ecb = company_ecb._update_currency_ecb()
        res_yah = company_yah._update_currency_yahoo()
        res_fta = company_fta._update_currency_fta()
        res_banxico = company_banxico._update_currency_banxico()

        #Check that all companies call to _update_currency_rates() has created a new rate for the USD (only if the request was a success)
        rates_number_again = len(self.currency_usd.rate_ids)
        self.assertEqual(rates_number + int(res_ecb) + int(res_yah) + int(res_fta) + int(res_banxico), rates_number_again)
