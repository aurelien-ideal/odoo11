# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import models, fields

class SDDXMLArchive(models.Model):
    """ This model represents the data that are archived every time a SDD XML file
    is generated. It used to keep track of which payment
    requests were sent and when, in case some technical problem caused the file
    not to be received properly by the bank.
    """
    _name = 'sdd.xml.archive'

    def _default_xml_filename(self):
        return 'PAIN008' + datetime.now().strftime('%Y%m%d%H%M%S') + '.xml'

    creation_date = fields.Date(string='Date of creation', default=fields.Date.today, readonly=True, help="Date of creation of this XML file.")
    payment_ids = fields.Many2many(string='Payments in file', comodel_name='account.payment', help="Payments contained in this XML file.")
    xml_file = fields.Binary(string='SEPA XML file', help="Archived XML file")
    xml_filename = fields.Char(string='SEPA XML file name', default=_default_xml_filename, help="Name of this XML file", store=True)
