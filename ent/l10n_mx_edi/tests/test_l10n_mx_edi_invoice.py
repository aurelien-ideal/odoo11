# coding: utf-8

import base64
import os

from lxml import etree, objectify

from odoo.tools import misc

from . import common


class TestL10nMxEdiInvoice(common.InvoiceTransactionCase):
    def setUp(self):
        super(TestL10nMxEdiInvoice, self).setUp()
        self.refund_model = self.env['account.invoice.refund']

        self.cert = misc.file_open(os.path.join(
            'l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.cer'), 'rb').read()
        self.cert_key = misc.file_open(os.path.join(
            'l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.key'), 'rb').read()
        self.cert_password = '12345678a'
        self.l10n_mx_edi_basic_configuration()
        self.xml_expected_str = misc.file_open(os.path.join(
            'l10n_mx_edi', 'tests', 'expected_cfdi32.xml'), mode='rb').read()
        self.xml_expected = objectify.fromstring(self.xml_expected_str)
        self.company_partner = self.env.ref('base.main_partner')
        self.payment_term = self.ref('account.account_payment_term_net')
        self.config_parameter = self.env.ref(
            'l10n_mx_edi.l10n_mx_edi_version_cfdi')

    def l10n_mx_edi_basic_configuration(self):
        self.company.write({
            'currency_id': self.mxn.id,
            'name': 'YourCompany',
        })
        self.company.partner_id.write({
            'vat': 'ACO560518KW7',
            'country_id': self.env.ref('base.mx').id,
            'state_id': self.env.ref('base.state_mx_jal').id,
            'street_name': 'Company Street Juan & José & "Niño"',
            'street2': 'Company Street 2',
            'street_number': 'Company Internal Number',
            'street_number2': 'Company Internal Number # 2',
            'l10n_mx_edi_colony': 'Company Colony',
            'l10n_mx_edi_locality': 'Company Locality',
            'city': 'Company City',
            'zip': '37200',
            'property_account_position_id': self.fiscal_position.id,
        })
        self.account_settings.create({
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_certificate_ids': [{
                'content': base64.encodestring(self.cert),
                'key': base64.encodestring(self.cert_key),
                'password': self.cert_password,
            }]
        }).execute()
        self.set_currency_rates(mxn_rate=21, usd_rate=1)

    def test_l10n_mx_edi_invoice_basic(self):
        # -----------------------
        # Testing sign process
        # -----------------------
        invoice = self.create_invoice()
        invoice.sudo().journal_id.l10n_mx_address_issued_id = self.company_partner.id
        invoice.move_name = 'INV/2017/999'
        invoice.action_invoice_open()
        self.assertEqual(invoice.state, "open")
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml = invoice.l10n_mx_edi_get_xml_etree()
        self.xml_merge_dynamic_items(xml, self.xml_expected)
        self.assertEqualXML(xml, self.xml_expected)
        xml_attach = base64.decodestring(invoice.l10n_mx_edi_cfdi)
        self.assertEqual(xml_attach.splitlines()[0].lower(),
                         b'<?xml version="1.0" encoding="utf-8"?>'.lower())

        # ----------------
        # Testing discount
        # ----------------
        invoice_disc = invoice.copy()
        for line in invoice_disc.invoice_line_ids:
            line.discount = 10
            line.price_unit = 500
        invoice_disc.compute_taxes()
        invoice_disc.action_invoice_open()
        self.assertEqual(invoice_disc.state, "open")
        self.assertEqual(invoice_disc.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml = invoice_disc.l10n_mx_edi_get_xml_etree()
        xml_expected_disc = objectify.fromstring(self.xml_expected_str)
        version = xml.get('version', xml.get('Version', ''))
        if version == '3.2':
            xml_expected_disc.attrib['subTotal'] = '500.00'
            xml_expected_disc.attrib['descuento'] = '50.00'
            # 500 - 10% + taxes(16%, -10%)
            xml_expected_disc.attrib['total'] = '477.00'
        elif version == '3.3':
            xml_expected_disc.attrib['SubTotal'] = '500.00'
            xml_expected_disc.attrib['Descuento'] = '50.00'
            # 500 - 10% + taxes(16%, -10%)
            xml_expected_disc.attrib['Total'] = '477.00'
        self.xml_merge_dynamic_items(xml, xml_expected_disc)
        if version == '3.2':
            xml_expected_disc.attrib['folio'] = xml.attrib['folio']
            xml_expected_disc.attrib['serie'] = xml.attrib['serie']
            for concepto in xml_expected_disc.Conceptos:
                concepto.Concepto.attrib['valorUnitario'] = '500.0'
                concepto.Concepto.attrib['importe'] = '500.0'
        elif version == '3.3':
            xml_expected_disc.attrib['Folio'] = xml.attrib['Folio']
            xml_expected_disc.attrib['Serie'] = xml.attrib['Serie']
            for concepto in xml_expected_disc.Conceptos:
                concepto.Concepto.attrib['ValorUnitario'] = '500.00'
                concepto.Concepto.attrib['Importe'] = '500.00'
                concepto.Concepto.attrib['Descuento'] = '50.00'
        self.assertEqualXML(xml, xml_expected_disc)

        # -----------------------
        # Testing re-sign process (recovery a previous signed xml)
        # -----------------------
        invoice.l10n_mx_edi_pac_status = "retry"
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "retry")
        invoice.l10n_mx_edi_update_pac_status()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml_attachs = invoice.l10n_mx_edi_retrieve_attachments()
        self.assertEqual(len(xml_attachs), 2)
        xml_1 = objectify.fromstring(base64.decodestring(xml_attachs[0].datas))
        xml_2 = objectify.fromstring(base64.decodestring(xml_attachs[1].datas))
        xml_2.remove(xml_2.Addenda)
        self.assertEqualXML(xml_1, xml_2)

        # -----------------------
        # Testing cancel PAC process
        # -----------------------
        invoice.sudo().journal_id.update_posted = True
        invoice.action_invoice_cancel()
        self.assertEqual(invoice.state, "cancel")
        self.assertEqual(invoice.l10n_mx_edi_pac_status, 'cancelled',
                         invoice.message_ids.mapped('body'))
        invoice.l10n_mx_edi_pac_status = "signed"

        # -----------------------
        # Testing cancel SAT process
        # -----------------------
        invoice.l10n_mx_edi_update_sat_status()
        self.assertNotEqual(invoice.l10n_mx_edi_sat_status, "cancelled")

        # Use a real UUID cancelled, only with CFDI version 3.2
        if version == '3.2':
            xml_tfd = invoice.l10n_mx_edi_get_tfd_etree(xml)
            xml_tfd.attrib['UUID'] = '0F481E0F-47A5-4647-B06B-8B471671F377'
            xml.Emisor.attrib['rfc'] = 'VAU111017CG9'
            xml.Receptor.attrib['rfc'] = 'IAL691030TK3'
            xml.attrib['total'] = '1.16'
            xml_attach = invoice.l10n_mx_edi_retrieve_last_attachment()
            xml_attach.datas = base64.encodestring(etree.tostring(xml))
            invoice.l10n_mx_edi_update_sat_status()
            self.assertEqual(invoice.l10n_mx_edi_sat_status, "cancelled",
                            invoice.message_ids.mapped('body'))

    def test_l10n_mx_edi_invoice_basic_sf(self):
        self.account_settings.create({'l10n_mx_edi_pac': 'solfact'}).execute()
        self.test_l10n_mx_edi_invoice_basic()

    def test_multi_currency(self):
        invoice = self.create_invoice()
        usd_rate = 20.0

        # -----------------------
        # Testing company.mxn.rate=1 and invoice.usd.rate=1/value
        # -----------------------
        self.set_currency_rates(mxn_rate=1, usd_rate=1/usd_rate)
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertEqual(float(values['rate']), usd_rate)

        # -----------------------
        # Testing company.mxn.rate=value and invoice.usd.rate=1
        # -----------------------
        self.set_currency_rates(mxn_rate=usd_rate, usd_rate=1)
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertEqual(float(values['rate']), usd_rate)

        # -----------------------
        # Testing using MXN currency for invoice and company
        # -----------------------
        invoice.currency_id = self.mxn.id
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertFalse(values['rate'])

    def test_addenda(self):
        invoice = self.create_invoice()
        addenda_autozone = self.ref('l10n_mx_edi.l10n_mx_edi_addenda_autozone')
        invoice.sudo().partner_id.l10n_mx_edi_addenda = addenda_autozone
        invoice.message_ids.unlink()
        invoice.action_invoice_open()
        self.assertEqual(invoice.state, "open")
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml_str = base64.decodestring(invoice.message_ids[-2].attachment_ids.datas)
        xml = objectify.fromstring(xml_str)
        xml_expected = objectify.fromstring(
            '<ADDENDA10 xmlns:cfdi="http://www.sat.gob.mx/cfd/3" '
            'DEPTID="DEPTID" VERSION="VERSION" BUYER="BUYER" VENDOR_ID="VENDOR_ID" POID="POID" PODATE="PODATE" '
            'EMAIL="%s"/>' % invoice.company_id.partner_id.email)
        xml_addenda = xml.Addenda.xpath('//ADDENDA10')[0]
        self.assertEqualXML(xml_addenda, xml_expected)

    def test_l10n_mx_edi_invoice_basic_33(self):
        isr_tag = self.env['account.account.tag'].search(
            [('name', '=', 'ISR')])
        self.config_parameter.value = '3.3'
        self.xml_expected_str = misc.file_open(os.path.join(
            'l10n_mx_edi', 'tests', 'expected_cfdi33.xml')).read().encode('UTF-8')
        self.xml_expected = objectify.fromstring(self.xml_expected_str)
        self.tax_negative.tag_ids |= isr_tag
        self.test_l10n_mx_edi_invoice_basic()

        # -----------------------
        # Testing invoice refund to verify CFDI related section
        # -----------------------
        invoice = self.create_invoice()
        invoice.action_invoice_open()
        refund = self.refund_model.with_context(
            active_ids=invoice.ids).create({
                'filter_refund': 'refund',
                'description': 'Refund Test',
                'date': invoice.date_invoice,
            })
        result = refund.invoice_refund()
        refund_id = result.get('domain')[1][2]
        refund = self.invoice_model.browse(refund_id)
        refund.action_invoice_open()
        xml = refund.l10n_mx_edi_get_xml_etree()
        self.assertEquals(xml.CfdiRelacionados.CfdiRelacionado.get('UUID'),
                          invoice.l10n_mx_edi_cfdi_uuid,
                          'Invoice UUID is different to CFDI related')
