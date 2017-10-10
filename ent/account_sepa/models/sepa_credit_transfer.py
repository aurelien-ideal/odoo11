# -*- coding: utf-8 -*-

import re
import time
import random
import base64

from lxml import etree

from odoo import models, fields, api, _
from odoo.tools import float_round, DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError, ValidationError


def check_valid_SEPA_str(string):
    if re.search('[^-A-Za-z0-9/?:().,\'+ ]', string) is not None:
        raise ValidationError(_("The text used in SEPA files can only contain the following characters :\n\n"
            "a b c d e f g h i j k l m n o p q r s t u v w x y z\n"
            "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z\n"
            "0 1 2 3 4 5 6 7 8 9\n"
            "/ - ? : ( ) . , ' + (space)"))

def prepare_SEPA_string(string):
    """ Make string comply with the recomandations of the EPC. See section 1.4 (Character Set) of document
        'sepa credit transfer scheme customer-to-bank implementation guidelines', issued by The European Payment Council.
    """
    if not string:
        return ''
    while '//' in string:  # No double slash allowed
        string = string.replace('//', '/')
    while string.startswith('/'):  # No leading slash allowed
        string = string[1:]
    while string.endswith('/'):  # No ending slash allowed
        string = string[:-1]
    string = re.sub('[^-A-Za-z0-9/?:().,\'+ ]', '', string)  # Only keep allowed characters
    return string


class AccountSepaCreditTransfer(models.TransientModel):
    _name = "account.sepa.credit.transfer"
    _description = "Create SEPA credit transfer files"

    @api.multi
    def _get_warning_message(self):
        for wiz in self:
            warning_message = self._context.get('warning_message', '')
            if warning_message:
                wiz.warning_message = _('The generated payment file is not a generic SEPA credit transfer. Be aware that some banks may reject it because it is not implemented on their side.\n\nIn particular, the reason why this payment file is not generic is the following:\n   ') + warning_message 

    journal_id = fields.Many2one('account.journal', string="Journal", readonly=True)
    bank_account_id = fields.Many2one('res.partner.bank', string="Bank Account", readonly=True)
    is_generic = fields.Boolean(readonly=True,
        help=u"Technical feature used during the file creation. A SEPA message is said to be 'generic' if it cannot be considered as "
             u"a standard european credit transfer. That is if the bank journal is not in €, a transaction is not in € or a payee is "
             u"not identified by an IBAN account number and a bank BIC.")
    warning_message = fields.Text(string='Warning', compute=_get_warning_message, store=False)
    file = fields.Binary('SEPA XML File', readonly=True)
    filename = fields.Char(string='Filename', size=256, readonly=True)

    @api.model
    def create_sepa_credit_transfer(self, payments):
        """ Create a new instance of this model then open a wizard allowing to download the file
        """
        # Since this method is called via a client_action_multi, we need to make sure the received records are what we expect
        payments = payments.filtered(lambda r: r.payment_method_id.code == 'sepa_ct' and r.state in ('posted', 'sent')).sorted(key=lambda r: r.id)

        if len(payments) == 0:
            raise UserError(_("Payments to export as SEPA Credit Transfer must have 'SEPA Credit Transfer' selected as payment method and be posted"))
        if any(payment.journal_id != payments[0].journal_id for payment in payments):
            raise UserError(_("In order to export a SEPA Credit Transfer file, please only select payments belonging to the same bank journal."))

        journal = payments[0].journal_id
        bank_account = journal.bank_account_id
        if not bank_account.acc_type == 'iban':
            raise UserError(_("The account %s, of journal '%s', is not of type IBAN.\nA valid IBAN account is required to use SEPA features.") % (bank_account.acc_number, journal.name))
        for payment in payments:
            if not payment.partner_bank_account_id:
                raise UserError(_("There is no bank account selected for payment '%s'") % payment.name)

        is_generic, warning_msg = self._require_generic_message(journal, payments)
        res = self.create({
            'journal_id': journal.id,
            'bank_account_id': bank_account.id,
            'filename': "SCT-" + journal.code + "-" + time.strftime("%Y%m%d") + ".xml",
            'is_generic': is_generic,
        })

        if journal.company_id.sepa_pain_version == 'pain.001.001.03.ch.02':
            xml_doc = res._create_pain_001_001_03_ch_document(payments)
        elif journal.company_id.sepa_pain_version == 'pain.001.003.03':
            xml_doc = res._create_pain_001_003_03_document(payments)
        else:
            xml_doc = res._create_pain_001_001_03_document(payments)
        res.file = base64.encodestring(xml_doc)

        payments.write({'state': 'sent'})
        payments.write({'payment_reference': res.filename})

        # Alternatively, return the id of the transient and use a controller to download the file
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.sepa.credit.transfer',
            'target': 'new',
            'res_id': res.id,
            'context': {'warning_message': warning_msg}
        }

    @api.model
    def _require_generic_message(self, journal, payments):
        """ Find out if generating a credit transfer initiation message for payments requires to use the generic rules, as opposed to the standard ones.
            The generic rules are used for payments which are not considered to be standard european credit transfers.
        """
        # A message is generic if :
        debtor_currency = journal.currency_id and journal.currency_id.name or journal.company_id.currency_id.name
        if debtor_currency != 'EUR':
            return True, _('Your bank account is not labelled in EUR')
        for payment in payments:
            bank_account = payment.partner_bank_account_id
            if payment.currency_id.name != 'EUR':
                return True, _('The transaction %s is instructed in another currency than EUR') % payment.name
            if not bank_account.bank_bic:
                return True, _('The creditor bank account %s used in payment %s is not identified by a BIC') % (payment.partner_bank_account_id.acc_number, payment.name)
            if not bank_account.acc_type == 'iban':
                return True, _('The creditor bank account %s used in payment %s is not identified by an IBAN') % (payment.partner_bank_account_id.acc_number, payment.name)
        return False, ''

    def _create_pain_001_001_03_document(self, doc_payments):
        """ Create a sepa credit transfer file that follows the European Payment Councile generic guidelines (pain.001.001.03)

            :param doc_payments: recordset of account.payment to be exported in the XML document returned
        """
        Document = self._create_iso20022_document('pain.001.001.03')
        return self._create_iso20022_credit_transfer(Document, doc_payments)

    def _create_pain_001_001_03_ch_document(self, doc_payments):
        """ Create a sepa credit transfer file that follows the swiss specific guidelines, as established
            by SIX Interbank Clearing (pain.001.001.03.ch.02)

            :param doc_payments: recordset of account.payment to be exported in the XML document returned
        """
        Document = etree.Element("Document", nsmap={
            None: "http://www.six-interbank-clearing.com/de/pain.001.001.03.ch.02.xsd",
            'xsi': "http://www.w3.org/2001/XMLSchema-instance"})
        return self._create_iso20022_credit_transfer(Document, doc_payments)

    def _create_pain_001_003_03_document(self, doc_payments):
        """ Create a sepa credit transfer file that follows the german specific guidelines, as established
            by the German Bank Association (Deutsche Kreditwirtschaft) (pain.001.003.03)

            :param doc_payments: recordset of account.payment to be exported in the XML document returned
        """
        Document = self._create_iso20022_document('pain.001.003.03')
        return self._create_iso20022_credit_transfer(Document, doc_payments)

    def _create_iso20022_document(self, pain_version):
        Document = etree.Element("Document", nsmap={
            None: "urn:iso:std:iso:20022:tech:xsd:%s" % (pain_version,),
            'xsi': "http://www.w3.org/2001/XMLSchema-instance"})
        return Document

    def _create_iso20022_credit_transfer(self, Document, doc_payments):
        CstmrCdtTrfInitn = etree.SubElement(Document, "CstmrCdtTrfInitn")

        # Create the GrpHdr XML block
        GrpHdr = etree.SubElement(CstmrCdtTrfInitn, "GrpHdr")
        MsgId = etree.SubElement(GrpHdr, "MsgId")
        val_MsgId = str(int(time.time() * 100))[-10:]
        val_MsgId = prepare_SEPA_string(self.journal_id.company_id.name[-15:]) + val_MsgId
        val_MsgId = str(random.random()) + val_MsgId
        val_MsgId = val_MsgId[-30:]
        MsgId.text = val_MsgId
        CreDtTm = etree.SubElement(GrpHdr, "CreDtTm")
        CreDtTm.text = time.strftime("%Y-%m-%dT%H:%M:%S")
        NbOfTxs = etree.SubElement(GrpHdr, "NbOfTxs")
        val_NbOfTxs = str(len(doc_payments))
        if len(val_NbOfTxs) > 15:
            raise ValidationError(_("Too many transactions for a single file."))
        if not self.bank_account_id.bank_bic:
            raise UserError(_("There is no Bank Identifier Code recorded for bank account '%s' of journal '%s'") % (self.bank_account_id.acc_number, self.journal_id.name))
        NbOfTxs.text = val_NbOfTxs
        CtrlSum = etree.SubElement(GrpHdr, "CtrlSum")
        CtrlSum.text = self._get_CtrlSum(doc_payments)
        GrpHdr.append(self._get_InitgPty())

        # Create one PmtInf XML block per execution date
        payments_date_wise = {}
        for payment in doc_payments:
            if payment.payment_date not in payments_date_wise:
                payments_date_wise[payment.payment_date] = []
            payments_date_wise[payment.payment_date].append(payment)
        count = 0
        for payment_date, payments_list in payments_date_wise.items():
            count += 1
            PmtInf = etree.SubElement(CstmrCdtTrfInitn, "PmtInf")
            PmtInfId = etree.SubElement(PmtInf, "PmtInfId")
            PmtInfId.text = (val_MsgId + str(self.journal_id.id) + str(count))[-30:]
            PmtMtd = etree.SubElement(PmtInf, "PmtMtd")
            PmtMtd.text = 'TRF'
            BtchBookg = etree.SubElement(PmtInf, "BtchBookg")
            BtchBookg.text = 'false'
            NbOfTxs = etree.SubElement(PmtInf, "NbOfTxs")
            NbOfTxs.text = str(len(payments_list))
            CtrlSum = etree.SubElement(PmtInf, "CtrlSum")
            CtrlSum.text = self._get_CtrlSum(payments_list)
            PmtInf.append(self._get_PmtTpInf())
            ReqdExctnDt = etree.SubElement(PmtInf, "ReqdExctnDt")
            ReqdExctnDt.text = time.strftime('%Y-%m-%d', time.strptime(payment_date, DEFAULT_SERVER_DATE_FORMAT))
            PmtInf.append(self._get_Dbtr())
            PmtInf.append(self._get_DbtrAcct())
            DbtrAgt = etree.SubElement(PmtInf, "DbtrAgt")
            FinInstnId = etree.SubElement(DbtrAgt, "FinInstnId")
            BIC = etree.SubElement(FinInstnId, "BIC")
            BIC.text = self.bank_account_id.bank_bic

            # One CdtTrfTxInf per transaction
            for payment in payments_list:
                PmtInf.append(self._get_CdtTrfTxInf(PmtInfId, payment))

        return etree.tostring(Document, pretty_print=True, xml_declaration=True, encoding='utf-8')

    def _get_CtrlSum(self, payments):
        return str(float_round(sum(payment.amount for payment in payments), 2))

    def _get_company_PartyIdentification32(self, org_id=True, postal_address=True):
        """ Returns a PartyIdentification32 element identifying the current journal's company
        """
        ret = []
        company = self.journal_id.company_id
        name_length = self.is_generic and 35 or 70

        Nm = etree.Element("Nm")
        Nm.text = prepare_SEPA_string(company.sepa_initiating_party_name[:name_length])
        ret.append(Nm)

        if postal_address and company.partner_id.city and company.partner_id.country_id.code:
            PstlAdr = etree.Element("PstlAdr")
            Ctry = etree.SubElement(PstlAdr, "Ctry")
            Ctry.text = company.partner_id.country_id.code
            if company.partner_id.street:
                AdrLine = etree.SubElement(PstlAdr, "AdrLine")
                AdrLine.text = prepare_SEPA_string(company.partner_id.street)
            if company.partner_id.zip and company.partner_id.city:
                AdrLine = etree.SubElement(PstlAdr, "AdrLine")
                AdrLine.text = prepare_SEPA_string(company.partner_id.zip) + " " + prepare_SEPA_string(company.partner_id.city)
            ret.append(PstlAdr)

        if org_id and company.sepa_orgid_id:
            Id = etree.Element("Id")
            OrgId = etree.SubElement(Id, "OrgId")
            Othr = etree.SubElement(OrgId, "Othr")
            _Id = etree.SubElement(Othr, "Id")
            _Id.text = prepare_SEPA_string(company.sepa_orgid_id)
            if company.sepa_orgid_issr:
                Issr = etree.SubElement(Othr, "Issr")
                Issr.text = prepare_SEPA_string(company.sepa_orgid_issr)
            ret.append(Id)

        return ret

    def _get_InitgPty(self):
        InitgPty = etree.Element("InitgPty")
        InitgPty.extend(self._get_company_PartyIdentification32(org_id=True, postal_address=False))
        return InitgPty

    def _get_PmtTpInf(self):
        PmtTpInf = etree.Element("PmtTpInf")
        InstrPrty = etree.SubElement(PmtTpInf, "InstrPrty")
        InstrPrty.text = 'NORM'

        if not self.is_generic:
            SvcLvl = etree.SubElement(PmtTpInf, "SvcLvl")
            Cd = etree.SubElement(SvcLvl, "Cd")
            Cd.text = 'SEPA'

        return PmtTpInf

    def _get_Dbtr(self):
        Dbtr = etree.Element("Dbtr")
        Dbtr.extend(self._get_company_PartyIdentification32(org_id=lambda: not self.is_generic, postal_address=True))
        return Dbtr

    def _get_DbtrAcct(self):
        DbtrAcct = etree.Element("DbtrAcct")
        Id = etree.SubElement(DbtrAcct, "Id")
        IBAN = etree.SubElement(Id, "IBAN")
        IBAN.text = self.bank_account_id.sanitized_acc_number
        Ccy = etree.SubElement(DbtrAcct, "Ccy")
        Ccy.text = self.journal_id.currency_id and self.journal_id.currency_id.name or self.journal_id.company_id.currency_id.name

        return DbtrAcct

    def _get_CdtTrfTxInf(self, PmtInfId, payment):
        CdtTrfTxInf = etree.Element("CdtTrfTxInf")
        PmtId = etree.SubElement(CdtTrfTxInf, "PmtId")
        InstrId = etree.SubElement(PmtId, "InstrId")
        InstrId.text = prepare_SEPA_string(payment.name)
        EndToEndId = etree.SubElement(PmtId, "EndToEndId")
        EndToEndId.text = (PmtInfId.text + str(payment.id))[-30:]
        Amt = etree.SubElement(CdtTrfTxInf, "Amt")
        val_Ccy = payment.currency_id and payment.currency_id.name or payment.journal_id.company_id.currency_id.name
        val_InstdAmt = str(float_round(payment.amount, 2))
        max_digits = val_Ccy == 'EUR' and 11 or 15
        if len(re.sub('\.', '', val_InstdAmt)) > max_digits:
            raise ValidationError(_("The amount of the payment '%s' is too high. The maximum permitted is %s.") % (payment.name, str(9) * (max_digits - 3) + ".99"))
        InstdAmt = etree.SubElement(Amt, "InstdAmt", Ccy=val_Ccy)
        InstdAmt.text = val_InstdAmt
        CdtTrfTxInf.append(self._get_ChrgBr())
        CdtTrfTxInf.append(self._get_CdtrAgt(payment.partner_bank_account_id))
        Cdtr = etree.SubElement(CdtTrfTxInf, "Cdtr")
        Nm = etree.SubElement(Cdtr, "Nm")
        Nm.text = prepare_SEPA_string(payment.partner_id.name[:70])
        if payment.payment_type == 'transfer':
           CdtTrfTxInf.append(self._get_CdtrAcct(payment.destination_journal_id.bank_account_id))
        else:
            CdtTrfTxInf.append(self._get_CdtrAcct(payment.partner_bank_account_id))
        val_RmtInf = self._get_RmtInf(payment)
        if val_RmtInf is not False:
            CdtTrfTxInf.append(val_RmtInf)
        return CdtTrfTxInf

    def _get_ChrgBr(self):
        ChrgBr = etree.Element("ChrgBr")
        ChrgBr.text = self.is_generic and "SHAR" or "SLEV"
        return ChrgBr

    def _get_CdtrAgt(self, bank_account):
        bank = bank_account.bank_id

        CdtrAgt = etree.Element("CdtrAgt")
        FinInstnId = etree.SubElement(CdtrAgt, "FinInstnId")
        val_BIC = bank_account.bank_bic
        if val_BIC:
            BIC = etree.SubElement(FinInstnId, "BIC")
            BIC.text = val_BIC
        elif not self.is_generic:
            raise UserError(_("There is no Bank Identifier Code recorded for bank account '%s'") % bank_account.acc_number)

        return CdtrAgt

    def _get_CdtrAcct(self, bank_account):
        if not self.is_generic and (not bank_account.acc_type or not bank_account.acc_type == 'iban'):
            raise UserError(_("The account %s, linked to partner '%s', is not of type IBAN.\nA valid IBAN account is required to use SEPA features.") % (bank_account.acc_number, bank_account.partner_id))

        CdtrAcct = etree.Element("CdtrAcct")
        Id = etree.SubElement(CdtrAcct, "Id")
        if self.is_generic:
            Othr = etree.SubElement(Id, "Othr")
            _Id = etree.SubElement(Othr, "Id")
            _Id.text = bank_account.acc_number
        else:
            IBAN = etree.SubElement(Id, "IBAN")
            IBAN.text = bank_account.sanitized_acc_number

        return CdtrAcct

    def _get_RmtInf(self, payment):
        if not payment.communication:
            return False
        RmtInf = etree.Element("RmtInf")
        Ustrd = etree.SubElement(RmtInf, "Ustrd")
        Ustrd.text = prepare_SEPA_string(payment.communication)
        return RmtInf
