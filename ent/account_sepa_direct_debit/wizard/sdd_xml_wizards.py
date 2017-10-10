# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import models, fields, _

from odoo.exceptions import ValidationError


class GenerateXMLWizard(models.TransientModel):
    """ Wizard allowing to set a collection date for payments when generating the
    SDD XML file collecting them.
    """
    _name = 'sdd.generate.xml.wizard'

    company_id = fields.Many2one(comodel_name='res.company',
                                 required=True,
                                 default=lambda self: self.env['res.company']._company_default_get('account.payment'),
                                 help="Company collecting the payments.")

    payments_to_send_ids = fields.Many2many(comodel_name='account.payment', required=True, help="Set of payments to (try to) put into a SDD XML file.")
    required_collection_date = fields.Date(string='Required collection date', default=fields.Date.today, required=True, help="Date when the company expects to be paid.")

    def validate_btn(self):
        """ Called by the 'validate' button of this wizard.
        """
        if not self.company_id.sdd_creditor_identifier:
            raise ValidationError(_("Your company must have a creditor identifier in order to issue SEPA Direct Debit payments requests. It can be defined in accounting module's settings."))

        payments_set = self.env['account.payment']
        payments_in_exception = []
        for payment in self.payments_to_send_ids:

            if payment.company_id == self.company_id \
                and payment.state == 'posted' \
                and payment.payment_method_code == 'sdd' \
                and payment.sdd_mandate_id.partner_bank_id.bank_id \
                and payment.sdd_mandate_id.partner_bank_id.bank_id.bic:

                payment.state = 'sent'
                payments_set += payment
            else:
                payments_in_exception.append(payment)

        xml_wizard = self.env['sdd.download.xml.wizard'].create({'payment_ids':[(4, payment.id, None) for payment in payments_set],
                                                     'payments_in_exception':[(4, payment.id, None) for payment in payments_in_exception],
                                                     'xml_file':base64.encodestring(payments_set.generate_xml(self.company_id, self.required_collection_date))})

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sdd.download.xml.wizard',
            'target': 'new',
            'res_id': xml_wizard.id,
        }


class SEPADirectDebitXMLWizard(models.TransientModel):
    """ Wizard allowing to download a SDD XML file once it has been generated and
    displaying informations about its generation.
    """
    _name = 'sdd.download.xml.wizard'

    archive_id = fields.Many2one(string='Archive for this operation',
                                 comodel_name='sdd.xml.archive',
                                 readonly=True,
                                 default=lambda self: self.env['sdd.xml.archive'].create({}),
                                 help="Archive data containing the generated XML.")

    payment_ids = fields.Many2many(string='Payments in file', comodel_name='account.payment', related='archive_id.payment_ids', help="Payments contained in the generated XML.")
    xml_file = fields.Binary(string='SEPA XML file', related='archive_id.xml_file', help="Generated XML file")
    xml_filename = fields.Char(string='SEPA XML file name', related='archive_id.xml_filename', help="Name of the generated XML file")
    payments_in_exception = fields.Many2many(string='Payments in exception', comodel_name='account.payment', help="Payments whose XML could not be generated because they had not been generated from a SEPA Direct Debit mandate.")
