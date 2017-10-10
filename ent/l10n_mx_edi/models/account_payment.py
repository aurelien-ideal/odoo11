# -*- coding: utf-8 -*-

import base64
from datetime import datetime
from itertools import groupby

from lxml import etree
from lxml.objectify import fromstring
from suds.client import Client
from odoo import _, api, fields, models
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools.misc import html_escape
from odoo.exceptions import UserError

from . import account_invoice

CFDI_TEMPLATE = 'l10n_mx_edi.payment10'
CFDI_XSLT_CADENA = 'l10n_mx_edi/data/3.3/cadenaoriginal.xslt'
CFDI_SAT_QR_STATE = {
    'No Encontrado': 'not_found',
    'Cancelado': 'cancelled',
    'Vigente': 'valid',
}


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_mx_edi_pac_status = fields.Selection(
        selection=[
            ('retry', 'Retry'),
            ('to_sign', 'To sign'),
            ('signed', 'Signed'),
            ('to_cancel', 'To cancel'),
            ('cancelled', 'Cancelled')
        ],
        string='PAC status',
        help='Refers to the status of the CFDI inside the PAC.',
        readonly=True, copy=False)
    l10n_mx_edi_sat_status = fields.Selection(
        selection=[
            ('none', 'State not defined'),
            ('undefined', 'Not Synced Yet'),
            ('not_found', 'Not Found'),
            ('cancelled', 'Cancelled'),
            ('valid', 'Valid'),
        ],
        string='SAT status',
        help='Refers to the status of the CFDI inside the SAT system.',
        readonly=True, copy=False, required=True,
        track_visibility='onchange', default='undefined')
    l10n_mx_edi_cfdi_name = fields.Char(string='CFDI name', copy=False, readonly=True,
        help='The attachment name of the CFDI.')
    l10n_mx_edi_payment_method_id = fields.Many2one(
        'l10n_mx_edi.payment.method',
        string='Payment Method',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Indicates the way the payment was/will be received, where the '
        'options could be: Cash, Nominal Check, Credit Card, etc.')
    l10n_mx_edi_cfdi = fields.Binary(
        string='Cfdi content', copy=False, readonly=True,
        help='The cfdi xml content encoded in base64.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_uuid = fields.Char(string='Fiscal Folio', copy=False, readonly=True,
        help='Folio in electronic invoice, is returned by SAT when send to stamp.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_certificate_id = fields.Many2one('l10n_mx_edi.certificate',
        string='Certificate', copy=False, readonly=True,
        help='The certificate used during the generation of the cfdi.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char('Supplier RFC', copy=False, readonly=True,
        help='The supplier tax identification number.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_customer_rfc = fields.Char('Customer RFC', copy=False, readonly=True,
        help='The customer tax identification number.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_origin = fields.Char(
        string='CFDI Origin', copy=False,
        help='In some cases the payment must be regenerated to fix data in it. '
        'In that cases is necessary this field filled, the format is: '
        '\n04|UUID1, UUID2, ...., UUIDn.\n'
        'Example:\n"04|89966ACC-0F5C-447D-AEF3-3EED22E711EE,89966ACC-0F5C-447D-AEF3-3EED22E711EE"')

    @api.multi
    def post(self):
        """Generate CFDI to payment after that invoice is paid"""
        res = super(AccountPayment, self).post()
        for record in self.filtered(lambda r: r.l10n_mx_edi_is_required()):
            record.l10n_mx_edi_cfdi_name = ('%s-%s-MX-Payment-10.xml' % (
                record.journal_id.code, record.name))
            self._l10n_mx_edi_retry()
        return res

    # -----------------------------------------------------------------------
    # Cancellation
    # -----------------------------------------------------------------------

    @api.multi
    def cancel(self):
        result = super(AccountPayment, self).cancel()
        for record in self.filtered(lambda r: r.l10n_mx_edi_is_required()):
            record._l10n_mx_edi_cancel()
        return result

    @api.multi
    def _l10n_mx_edi_cancel(self):
        """Call the cancel service with records that can be cancelled."""
        records = self.search([
            ('l10n_mx_edi_pac_status', 'in', ['to_sign', 'signed', 'to_cancel', 'retry']),
            ('id', 'in', self.ids)])
        for record in records:
            if record.l10n_mx_edi_pac_status in ['to_sign', 'retry']:
                record.l10n_mx_edi_pac_status = 'cancelled'
                record.message_post(body=_('The cancel service has been called with success'))
            else:
                record.l10n_mx_edi_pac_status = 'to_cancel'
        records = self.search([
            ('l10n_mx_edi_pac_status', '=', 'to_cancel'),
            ('id', 'in', self.ids)])
        records._l10n_mx_edi_call_service('cancel')

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def l10n_mx_edi_retrieve_attachments(self):
        """Retrieve all the cfdi attachments generated for this payment.

        :return: An ir.attachment recordset
        """
        self.ensure_one()
        if not self.l10n_mx_edi_cfdi_name:
            return []
        domain = [
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
            ('name', '=', self.l10n_mx_edi_cfdi_name)]
        return self.env['ir.attachment'].search(domain)

    @api.model
    def l10n_mx_edi_retrieve_last_attachment(self):
        attachment_ids = self.l10n_mx_edi_retrieve_attachments()
        return attachment_ids and attachment_ids[0] or None

    @api.model
    def l10n_mx_edi_get_xml_etree(self, cfdi=None):
        '''Get an objectified tree representing the cfdi.
        If the cfdi is not specified, retrieve it from the attachment.

        :param cfdi: The cfdi as string
        :return: An objectified tree
        '''
        #TODO helper which is not of too much help and should be removed
        self.ensure_one()
        if cfdi is None:
            cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        return fromstring(cfdi)

    @api.model
    def l10n_mx_edi_get_tfd_etree(self, cfdi):
        '''Get the TimbreFiscalDigital node from the cfdi.

        :param cfdi: The cfdi as etree
        :return: the TimbreFiscalDigital node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_payment_etree(self, cfdi):
        '''Get the Complement node from the cfdi.

        :param cfdi: The cfdi as etree
        :return: the Payment node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = '//pago10:DoctoRelacionado'
        namespace = {'pago10': 'http://www.sat.gob.mx/Pagos'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node

    @api.model
    def _get_l10n_mx_edi_cadena(self):
        self.ensure_one()
        #get the xslt path
        xslt_path = CFDI_XSLT_CADENA
        #get the cfdi as eTree
        cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        cfdi = self.l10n_mx_edi_get_xml_etree(cfdi)
        #return the cadena
        return self.env['account.invoice'].l10n_mx_edi_generate_cadena(xslt_path, cfdi)

    @api.multi
    def l10n_mx_edi_is_required(self):
        self.ensure_one()
        version = self.env['account.invoice'].l10n_mx_edi_get_pac_version()
        required = (self.payment_type == 'inbound' and
                self.company_id.country_id == self.env.ref('base.mx') and
                version == '3.3')
        if not required:
            return required
        if not self.invoice_ids:
            raise UserError(_(
                'Is necessary assign the invoices that are paid with this '
                'payment to allow relate in the CFDI the fiscal '
                'documents that are affected with this record.'))
        if False in self.invoice_ids.mapped('l10n_mx_edi_cfdi_uuid'):
            raise UserError(_(
                'Some of the invoices that will be paid with this record '
                'is not signed, and the UUID is required to indicate '
                'the invoices that are paid with this CFDI'))
        if not self.invoice_ids.filtered(lambda i: i.date_invoice != self.payment_date):
            return False
        return required

    @api.multi
    def l10n_mx_edi_log_error(self, message):
        self.ensure_one()
        self.message_post(body=_('Error during the process: %s') % message)

    @api.multi
    @api.depends('l10n_mx_edi_cfdi_name')
    def _compute_cfdi_values(self):
        """Fill the invoice fields from the cfdi values."""
        for rec in self:
            attachment_id = rec.l10n_mx_edi_retrieve_last_attachment()
            if not attachment_id:
                continue
            attachment_id = attachment_id[0]
            # At this moment, the attachment contains the file size in its 'datas' field because
            # to save some memory, the attachment will store its data on the physical disk.
            # To avoid this problem, we read the 'datas' directly on the disk.
            datas = attachment_id._file_read(attachment_id.store_fname)
            rec.l10n_mx_edi_cfdi = datas
            tree = rec.l10n_mx_edi_get_xml_etree(base64.decodestring(datas))
            tfd_node = rec.l10n_mx_edi_get_tfd_etree(tree)
            if tfd_node is not None:
                rec.l10n_mx_edi_cfdi_uuid = tfd_node.get('UUID')
            rec.l10n_mx_edi_cfdi_supplier_rfc = tree.Emisor.get('rfc')
            rec.l10n_mx_edi_cfdi_customer_rfc = tree.Receptor.get('rfc')
            certificate = tree.get('noCertificado', tree.get('NoCertificado'))
            rec.l10n_mx_edi_cfdi_certificate_id = self.env['l10n_mx_edi.certificate'].sudo().search(
                [('serial_number', '=', certificate)], limit=1)

    @api.multi
    def _l10n_mx_edi_retry(self):
        for rec in self:
            cfdi_values = rec._l10n_mx_edi_create_cfdi_payment()
            error = cfdi_values.pop('error', None)
            cfdi = cfdi_values.pop('cfdi', None)
            if error:
                # cfdi failed to be generated
                rec.l10n_mx_edi_pac_status = 'retry'
                rec.message_post(body=error)
                continue
            # cfdi has been successfully generated
            rec.l10n_mx_edi_pac_status = 'to_sign'
            filename = ('%s-%s-MX-Payment-10.xml' % (
                rec.journal_id.code, rec.name))
            ctx = self.env.context.copy()
            ctx.pop('default_type', False)
            rec.l10n_mx_edi_cfdi_name = filename
            attachment_id = self.env['ir.attachment'].with_context(ctx).create({
                'name': filename,
                'res_id': rec.id,
                'res_model': rec._name,
                'datas': base64.encodestring(cfdi),
                'datas_fname': filename,
                'description': _('Mexican CFDI to payment'),
                })
            rec.message_post(
                body=_('CFDI document generated (may be not signed)'),
                attachment_ids=[attachment_id.id])
            rec._l10n_mx_edi_sign()

    @api.multi
    def _l10n_mx_edi_create_cfdi_payment(self):
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        pac_name = company_id.l10n_mx_edi_pac
        values = self._l10n_mx_edi_create_cfdi_values()

        # -----------------------
        # Check the configuration
        # -----------------------
        # -Check certificate
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        if not certificate_id:
            error_log.append(_('No valid certificate found'))

        # -Check PAC
        if pac_name:
            pac_test_env = company_id.l10n_mx_edi_pac_test_env
            pac_username = company_id.l10n_mx_edi_pac_username
            pac_password = company_id.l10n_mx_edi_pac_password
            if not pac_test_env and not (pac_username and pac_password):
                error_log.append(_('No PAC credentials specified.'))
        else:
            error_log.append(_('No PAC specified.'))

        if error_log:
            return {'error': _('Please check your configuration: ') + account_invoice.create_list_html(error_log)}

        # -Compute date and time of the invoice
        date_mx = self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime()
        time_invoice = date_mx.strftime(DEFAULT_SERVER_TIME_FORMAT)

        # -----------------------
        # Create the EDI document
        # -----------------------

        # -Compute certificate data
        values['date'] = datetime.combine(
            fields.Datetime.from_string(self.payment_date),
            datetime.strptime(time_invoice, '%H:%M:%S').time()).strftime('%Y-%m-%dT%H:%M:%S')
        values['certificate_number'] = certificate_id.serial_number
        values['certificate'] = certificate_id.sudo().get_data()[0]

        # -Compute cfdi
        cfdi = qweb.render(CFDI_TEMPLATE, values=values)

        # -Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        cadena = self.env['account.invoice'].l10n_mx_edi_generate_cadena(
            CFDI_XSLT_CADENA, tree)

        # Post append cadena
        tree.attrib['Sello'] = certificate_id.sudo().get_encrypted_cadena(cadena)

        # TODO - Check with XSD
        return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}

    @api.multi
    def _l10n_mx_edi_create_cfdi_values(self):
        """Create the values to fill the CFDI template with complement to
        payments."""
        self.ensure_one()
        invoice_obj = self.env['account.invoice']
        precision_digits = self.env['decimal.precision'].precision_get('Account')
        values = {
            'record': self,
            'supplier': self.company_id.partner_id.commercial_partner_id,
            'customer': self.partner_id.commercial_partner_id,
            'fiscal_position': self.company_id.partner_id.property_account_position_id,
            'invoice': invoice_obj,
        }

        values.update(invoice_obj._l10n_mx_get_serie_and_folio(self.name))

        values['decimal_precision'] = precision_digits
        values.update(self.l10n_mx_edi_payment_data())
        return values

    @api.multi
    def get_cfdi_related(self):
        """To node CfdiRelacionados get documents related with each invoice
        from l10n_mx_edi_origin, hope the next structure:
            relation type|UUIDs separated by ,"""
        self.ensure_one()
        if not self.l10n_mx_edi_origin:
            return {}
        origin = self.l10n_mx_edi_origin.split('|')
        uuids = origin[1].split(',') if len(origin) > 1 else []
        return {
            'type': origin[0],
            'related': [u.strip() for u in uuids],
            }

    @api.multi
    def l10n_mx_edi_payment_data(self):
        self.ensure_one()
        # Based on "En caso de no contar con la hora se debe registrar 12:00:00"
        mxn = self.env.ref('base.MXN')
        precision_digits = self.env['decimal.precision'].precision_get('Account')
        date = datetime.combine(
            fields.Datetime.from_string(self.payment_date),
            datetime.strptime('12:00:00', '%H:%M:%S').time()).strftime('%Y-%m-%dT%H:%M:%S')
        rate = ('%0.*f' % (
            precision_digits,
            self.currency_id.with_context(date=self.payment_date).compute(
                1, mxn))) if self.currency_id.name != 'MXN' else False
        return {
            'mxn': mxn,
            'payment_date': date,
            'payment_rate': rate,
            'pay_vat_ord': False,
            'pay_account_ord': False,
            'pay_vat_receiver': False,
            'pay_account_receiver': False,
            'pay_ent_type': False,
            'pay_certificate': False,
            'pay_string': False,
            'pay_stamp': False,
        }

    @api.multi
    def _l10n_mx_edi_sign(self):
        """Call the sign service with records that can be signed."""
        records = self.search([
            ('l10n_mx_edi_pac_status', 'not in', ['signed', 'to_cancel', 'cancelled', 'retry']),
            ('id', 'in', self.ids)])
        records._l10n_mx_edi_call_service('sign')

    @api.multi
    def _l10n_mx_edi_post_cancel_process(self, cancelled, code=None, msg=None):
        '''Post process the results of the cancel service.

        :param cancelled: is the cancel has been done with success
        :param code: an eventual error code
        :param msg: an eventual error msg
        '''

        self.ensure_one()
        if cancelled:
            body_msg = _('The cancel service has been called with success')
            self.l10n_mx_edi_pac_status = 'cancelled'
            legal = _(
                '''<h3 style="color:red">Legal warning</h3>
                <p> Regarding the issue of the CFDI with' Complement for
                receipt of payments', where there are errors in the receipt, this
                may be canceled provided it is replaced by another with the correct data.
                If the error consists in which the payment receipt
                complement should not have been issued because the consideration
                had already been paid in full; replaced by another with an
                amount of one peso.</p>
                <p><a href="http://www.sat.gob.mx/informacion_fiscal/factura_electronica/Documents/Complementoscfdi/Guia_comple_pagos.pdf">
                For more information here (Pag. 5)</a></p>''')
            self.message_post(body=legal, message_type='notification')
        else:
            body_msg = _('The cancel service requested failed')
        post_msg = []
        if code:
            post_msg.extend([_('Code: ') + str(code)])
        if msg:
            post_msg.extend([_('Message: ') + msg])
        self.message_post(
            body=body_msg + account_invoice.create_list_html(post_msg))

    @api.multi
    def _l10n_mx_edi_call_service(self, service_type):
        """Call the right method according to the pac_name, it's info returned
        by the '_l10n_mx_edi_%s_info' % pac_name'
        method and the service_type passed as parameter.
        :param service_type: sign or cancel"""
        invoice_obj = self.env['account.invoice']
        # Regroup the invoices by company (= by pac)
        comp_x_records = groupby(self, lambda r: r.company_id)
        for company_id, records in comp_x_records:
            pac_name = company_id.l10n_mx_edi_pac
            if not pac_name:
                continue
            # Get the informations about the pac
            pac_info_func = '_l10n_mx_edi_%s_info' % pac_name
            service_func = '_l10n_mx_edi_%s_%s' % (pac_name, service_type)
            pac_info = getattr(invoice_obj, pac_info_func)(company_id, service_type)
            # Call the service with invoices one by one or all together according to the 'multi' value.
            # TODO - Check multi
            for record in records:
                getattr(record, service_func)(pac_info)

    # -------------------------------------------------------------------------
    # SAT/PAC service methods
    # -------------------------------------------------------------------------

    @api.model
    def _l10n_mx_edi_solfact_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.l10n_mx_edi_pac_username
        password = company_id.l10n_mx_edi_pac_password
        url = 'https://testing.solucionfactible.com/ws/services/Timbrado?wsdl'\
            if test else 'https://solucionfactible.com/ws/services/Timbrado?wsdl'
        return {
            'url': url,
            'multi': False,  # TODO: implement multi
            'username': 'testing@solucionfactible.com' if test else username,
            'password': 'timbrado.SF.16672' if test else password,
        }

    @api.multi
    def _l10n_mx_edi_solfact_sign(self, pac_info):
        '''SIGN for Solucion Factible.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            cfdi = rec.l10n_mx_edi_cfdi.decode('UTF-8')
            try:
                client = Client(url, timeout=20)
                response = client.service.timbrar(username, password, cfdi, False)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            msg = getattr(response.resultados[0], 'mensaje', None)
            code = getattr(response.resultados[0], 'status', None)
            xml_signed = getattr(response.resultados[0], 'cfdiTimbrado', None)
            rec._l10n_mx_edi_post_sign_process(xml_signed, code, msg)

    @api.multi
    def _l10n_mx_edi_solfact_cancel(self, pac_info):
        '''CANCEL for Solucion Factible.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            uuids = [rec.l10n_mx_edi_cfdi_uuid]
            certificate_id = rec.l10n_mx_edi_cfdi_certificate_id.sudo()
            cer_pem = base64.encodestring(certificate_id.get_pem_cer(
                certificate_id.content)).decode('UTF-8')
            key_pem = base64.encodestring(certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)).decode('UTF-8')
            key_password = certificate_id.password
            try:
                client = Client(url, timeout=20)
                response = client.service.cancelar(username, password, uuids, cer_pem, key_pem, key_password)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            code = getattr(response.resultados[0], 'statusUUID', None)
            cancelled = code in ('201', '202')  # cancelled or previously cancelled
            # no show code and response message if cancel was success
            msg = '' if cancelled else getattr(response.resultados[0], 'mensaje', None)
            code = '' if cancelled else code
            rec._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    @api.multi
    def _l10n_mx_edi_finkok_sign(self, pac_info):
        """SIGN for Finkok."""
        # TODO - Duplicated with the invoice one
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            cfdi = [rec.l10n_mx_edi_cfdi.decode('UTF-8')]
            try:
                client = Client(url, timeout=20)
                response = client.service.stamp(cfdi, username, password)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            code = 0
            msg = None
            if response.Incidencias:
                code = getattr(response.Incidencias[0][0], 'CodigoError', None)
                msg = getattr(response.Incidencias[0][0], 'MensajeIncidencia', None)
            xml_signed = getattr(response, 'xml', None)
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed.encode('utf-8'))
            rec._l10n_mx_edi_post_sign_process(xml_signed, code, msg)

    @api.multi
    def _l10n_mx_edi_finkok_cancel(self, pac_info):
        '''CANCEL for Finkok.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for inv in self:
            uuid = inv.l10n_mx_edi_cfdi_uuid
            certificate_id = inv.l10n_mx_edi_cfdi_certificate_id.sudo()
            company_id = self.company_id
            cer_pem = base64.encodestring(certificate_id.get_pem_cer(
                certificate_id.content)).decode('UTF-8')
            key_pem = base64.encodestring(certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)).decode('UTF-8')
            cancelled = False
            code = False
            try:
                client = Client(url, timeout=20)
                invoices_list = client.factory.create("UUIDS")
                invoices_list.uuids.string = [uuid]
                response = client.service.cancel(invoices_list, username, password, company_id.vat, cer_pem, key_pem)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            if not hasattr(response, 'Folios'):
                msg = _('A delay of 2 hours has to be respected before to cancel')
            else:
                code = getattr(response.Folios[0][0], 'EstatusUUID', None)
                cancelled = code in ('201', '202')  # cancelled or previously cancelled
                # no show code and response message if cancel was success
                code = '' if cancelled else code
                msg = '' if cancelled else _("Cancelling got an error")
            inv._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    @api.multi
    def _l10n_mx_edi_post_sign_process(self, xml_signed, code=None, msg=None):
        """Post process the results of the sign service.

        :param xml_signed: the xml signed datas codified in base64
        :param code: an eventual error code
        :param msg: an eventual error msg
        """
        # TODO - Duplicated
        self.ensure_one()
        if xml_signed:
            body_msg = _('The sign service has been called with success')
            # Update the pac status
            self.l10n_mx_edi_pac_status = 'signed'
            self.l10n_mx_edi_cfdi = xml_signed
            # Update the content of the attachment
            attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
            attachment_id.write({
                'datas': xml_signed,
                'mimetype': 'application/xml'
            })
            post_msg = [_('The content of the attachment has been updated')]
        else:
            body_msg = _('The sign service requested failed')
            post_msg = []
        if code:
            post_msg.extend([_('Code: ') + str(code)])
        if msg:
            post_msg.extend([_('Message: ') + msg])
        self.message_post(
            body=body_msg + account_invoice.create_list_html(post_msg))

    @api.multi
    def l10n_mx_edi_update_pac_status(self):
        """Synchronize both systems: Odoo & PAC if the invoices need to be
        signed or cancelled."""
        # TODO - Duplicated
        for record in self:
            if record.l10n_mx_edi_pac_status == 'to_sign':
                record._l10n_mx_edi_sign()
            elif record.l10n_mx_edi_pac_status == 'to_cancel':
                record._l10n_mx_edi_cancel()
            elif record.l10n_mx_edi_pac_status == 'retry':
                record._l10n_mx_edi_retry()

    @api.multi
    def l10n_mx_edi_update_sat_status(self):
        """Synchronize both systems: Odoo & SAT to make sure the invoice is valid.
        """
        url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
        for rec in self.filtered(lambda r: r.l10n_mx_edi_is_required() and
                                 r.l10n_mx_edi_pac_status in ['signed', 'cancelled']):
            supplier_rfc = rec.l10n_mx_edi_cfdi_supplier_rfc
            customer_rfc = rec.l10n_mx_edi_cfdi_customer_rfc
            total = 0
            uuid = rec.l10n_mx_edi_cfdi_uuid
            params = '"?re=%s&rr=%s&tt=%s&id=%s' % (
                html_escape(html_escape(supplier_rfc or '')),
                html_escape(html_escape(customer_rfc or '')),
                total or 0.0, uuid or '')
            try:
                response = Client(url).service.Consulta(params).Estado
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            rec.l10n_mx_edi_sat_status = CFDI_SAT_QR_STATE.get(response.__repr__(), 'none')

    @api.multi
    def _set_cfdi_origin(self, uuid):
        """Try to write the origin in of the CFDI, it is important in order
        to have a centralized way to manage this elements due to the fact
        that this logic can be used in several places functionally speaking
        all around Odoo.
        :param uuid:
        :return:
        """
        self.ensure_one()
        origin = '04|%s' % uuid
        self.update({'l10n_mx_edi_origin': origin})
        return origin

    @api.multi
    def action_draft(self):
        for record in self.filtered('l10n_mx_edi_cfdi_uuid'):
            record.l10n_mx_edi_origin = self._set_cfdi_origin(record.l10n_mx_edi_cfdi_uuid)
        return super(AccountPayment, self).action_draft()


class AccountRegisterPayments(models.TransientModel):
    _inherit = 'account.register.payments'

    l10n_mx_edi_payment_method_id = fields.Many2one(
        'l10n_mx_edi.payment.method',
        string='Payment Method',
        help='Indicates the way the payment was/will be received, where the '
        'options could be: Cash, Nominal Check, Credit Card, etc.')

    def _prepare_payment_vals(self, invoices):
        res = super(AccountRegisterPayments, self)._prepare_payment_vals(
            invoices)
        res.update({
            'l10n_mx_edi_payment_method_id': self.l10n_mx_edi_payment_method_id.id,
        })
        return res
