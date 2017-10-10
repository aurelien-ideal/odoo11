# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from datetime import datetime

from odoo import models, fields, api, _

from odoo.exceptions import UserError

from odoo.tools.float_utils import float_repr
from odoo.tools.xml_utils import create_xml_node, create_xml_node_chain

from lxml import etree


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    sdd_mandate_id = fields.Many2one(string='Originating SEPA mandate',
                                     comodel_name='sdd.mandate',
                                     readonly=True,
                                     help="The mandate used to generate this payment, if any.")
    sdd_mandate_usable = fields.Boolean(string="Could a SDD mandate be used?",
        help="Technical field used to inform the end user there is a SDD mandate that could be used to register that payment",
        compute='_compute_usable_mandate',)

    @api.depends('payment_date', 'partner_id', 'company_id')
    def _compute_usable_mandate(self):
        """ returns the first mandate found that can be used for this payment,
        or none if there is no such mandate.
        """
        sdd_mandate_obj = self.env['sdd.mandate']
        for payment in self:
            payment.sdd_mandate_usable = bool(sdd_mandate_obj._get_usable_mandate(
                payment.company_id.id or self.env.user.company_id.id,
                payment.partner_id.id,
                payment.payment_date))

    def generate_xml(self, company_id, required_collection_date):
        """ Generates a SDD XML file containing the payments corresponding to this recordset,
        associating them to the given company, with the specified
        collection date.
        """
        document = etree.Element("Document",nsmap={None:'urn:iso:std:iso:20022:tech:xsd:pain.008.001.02', 'xsi': "http://www.w3.org/2001/XMLSchema-instance"})
        CstmrDrctDbtInitn = etree.SubElement(document, 'CstmrDrctDbtInitn')

        self._sdd_xml_gen_header(company_id, CstmrDrctDbtInitn)

        payments_per_mandate = self._group_payments_per_mandate()
        payment_info_counter = 0
        for (mandate, mandate_payments) in payments_per_mandate.items():
            mandate_payments._sdd_xml_gen_partner(company_id, required_collection_date, payment_info_counter, mandate, CstmrDrctDbtInitn)
            payment_info_counter += 1

        return etree.tostring(document, pretty_print=True, xml_declaration=True, encoding='utf-8')

    def _sdd_xml_gen_header(self, company_id, CstmrDrctDbtInitn):
        """ Generates the header of the SDD XML file.
        """
        GrpHdr = create_xml_node(CstmrDrctDbtInitn, 'GrpHdr')
        create_xml_node(GrpHdr, 'MsgId', str(time.time()))  # Using time makes sure the identifier is unique in an easy way
        create_xml_node(GrpHdr, 'CreDtTm', datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
        create_xml_node(GrpHdr, 'NbOfTxs', str(len(self)))
        create_xml_node(GrpHdr, 'CtrlSum', float_repr(sum(x.amount for x in self), precision_digits=2))  # This sum ignores the currency, it is used as a checksum (see SEPA rulebook)
        create_xml_node_chain(GrpHdr, ['InitgPty','Id','PrvtId','Othr','Id'], company_id.sdd_creditor_identifier)

    def _sdd_xml_gen_partner(self, company_id, required_collection_date, payment_info_counter, mandate, CstmrDrctDbtInitn):
        """ Appends to a SDD XML file being generated all the data related to a partner
        and his payments. self must be a recordset whose payments share the same partner.
        """
        PmtInf = create_xml_node(CstmrDrctDbtInitn, 'PmtInf')
        create_xml_node(PmtInf, 'PmtInfId', str(payment_info_counter))
        create_xml_node(PmtInf, 'PmtMtd', 'DD')
        create_xml_node(PmtInf, 'NbOfTxs', str(len(self)))
        create_xml_node(PmtInf, 'CtrlSum', float_repr(sum(x.amount for x in self), precision_digits=2))  # This sum ignores the currency, it is used as a checksum (see SEPA rulebook)

        PmtTpInf = create_xml_node_chain(PmtInf, ['PmtTpInf','SvcLvl','Cd'], 'SEPA')[0]
        create_xml_node_chain(PmtTpInf, ['LclInstrm','Cd'], 'CORE')
        create_xml_node(PmtTpInf, 'SeqTp', 'FRST')
        #Note: FRST refers to the COLLECTION of payments, not the type of mandate used
        #This value is only used for informatory purpose.

        create_xml_node(PmtInf, 'ReqdColltnDt', fields.Date.from_string(required_collection_date).strftime("%Y-%m-%d"))
        create_xml_node_chain(PmtInf, ['Cdtr','Nm'], company_id.name[:70])  # SEPA regulation gives a maximum size of 70 characters for this field
        create_xml_node_chain(PmtInf, ['CdtrAcct','Id','IBAN'], mandate.payment_journal_id.bank_account_id.sanitized_acc_number)
        create_xml_node_chain(PmtInf, ['CdtrAgt','FinInstnId','BIC'], mandate.payment_journal_id.bank_id.bic)

        CdtrSchmeId_Othr = create_xml_node_chain(PmtInf, ['CdtrSchmeId','Id','PrvtId','Othr','Id'], company_id.sdd_creditor_identifier)[-2]
        create_xml_node_chain(CdtrSchmeId_Othr, ['SchmeNm','Prtry'], 'SEPA')

        partner = None
        for partner_payment in self:
            if not partner:
                partner = partner_payment.partner_id
            elif partner != partner_payment.partner_id:
                raise UserError("Trying to generate a single XML payment group for payments with different partners.")

            end2end_counter = 0
            partner_payment.sdd_xml_gen_payment(company_id, mandate.partner_id, end2end_counter, PmtInf)
            end2end_counter += 1

    def sdd_xml_gen_payment(self,company_id, partner, end2end_counter, PmtInf):
        """ Appends to a SDD XML file being generated all the data related to the
        payments of a given partner.
        """
        #The two following conditions should never execute.
        #They are here to be sure future modifications won't ever break everything.
        if self.company_id != company_id:
            raise UserError(_("Trying to generate a Direct Debit XML file containing payments from another company than that file's creditor."))

        if self.payment_method_id.code != 'sdd':
            raise UserError(_("Trying to generate a Direct Debit XML for payments coming from another payment method than SEPA Direct Debit."))

        DrctDbtTxInf = create_xml_node_chain(PmtInf, ['DrctDbtTxInf','PmtId','EndToEndId'], str(end2end_counter))[0]

        InstdAmt = create_xml_node(DrctDbtTxInf, 'InstdAmt', float_repr(self.amount, precision_digits=2))
        InstdAmt.attrib['Ccy'] = self.currency_id.name

        MndtRltdInf = create_xml_node_chain(DrctDbtTxInf, ['DrctDbtTx','MndtRltdInf','MndtId'], self.sdd_mandate_id.name)[-2]
        create_xml_node(MndtRltdInf, 'DtOfSgntr', self.sdd_mandate_id.start_date)
        create_xml_node_chain(DrctDbtTxInf, ['DbtrAgt','FinInstnId','BIC'], self.sdd_mandate_id.partner_bank_id.bank_id.bic)
        Dbtr = create_xml_node_chain(DrctDbtTxInf, ['Dbtr','Nm'], partner.name)[0]

        if self.sdd_mandate_id.debtor_id_code:
            create_xml_node(Dbtr, 'Id', self.sdd_mandate_id.debtor_id_code)

        if partner.contact_address:
            PstlAdr = create_xml_node(Dbtr, 'PstlAdr')
            if partner.country_id and partner.country_id.code:
                create_xml_node(PstlAdr, 'Ctry', partner.country_id.code)
            create_xml_node(PstlAdr, 'AdrLine', partner.contact_address)

        create_xml_node_chain(DrctDbtTxInf, ['DbtrAcct','Id','IBAN'], self.sdd_mandate_id.partner_bank_id.sanitized_acc_number)

    def _group_payments_per_mandate(self):
        """ Groups the payments of this recordset per associated mandate, in a dictionnary of recordsets.
        """
        rslt = {}
        for payment in self:
            if rslt.get(payment.sdd_mandate_id, False):
                rslt[payment.sdd_mandate_id] += payment
            else:
                rslt[payment.sdd_mandate_id] = payment
        return rslt

    def _register_on_mandate(self, mandate):
        for record in self:
            if mandate.partner_id != record.partner_id:
                raise UserError(_("Trying to register a payment on a mandate belonging to a different partner."))

            record.sdd_mandate_id = mandate
            mandate.write({'paid_invoice_ids': [(4, invoice.id, None) for invoice in record.invoice_ids]})

            if mandate.one_off:
                mandate.action_close_mandate()

    def action_validate_invoice_payment(self):
        """ Overridden to register the payment on mandate after posting it if
        it was made via SDD.
        """
        super(AccountPayment, self).action_validate_invoice_payment()

        for record in self:
            if record.payment_method_code == 'sdd':
                mandate = record.invoice_ids._get_usable_mandate() # Call to super() ensures there is only one invoice in the set
                if not mandate:
                    raise UserError(_("This invoice cannot be paid via SEPA Direct Debit, as there is no valid mandate available for its customer at its creation date."))
                record._register_on_mandate(mandate)


class AccountRegisterPaymentsWizard(models.TransientModel):
    _inherit = "account.register.payments"

    def create_payments(self):
        if self.payment_method_code == 'sdd':
            rslt = self.env['account.payment']
            for invoice in self.invoice_ids:
                mandate = invoice._get_usable_mandate()
                if not mandate:
                    raise UserError(_("This invoice cannot be paid via SEPA Direct Debit, as there is no valid mandate available for its customer at its creation date."))
                rslt += invoice.pay_with_mandate(mandate)
            return rslt

        return super(AccountRegisterPaymentsWizard, self).create_payments()
