# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
from contextlib import closing
from os.path import join, dirname, realpath
from lxml import etree, objectify

from odoo import api, tools, SUPERUSER_ID
import requests

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    _load_product_sat_catalog(cr, registry)
    _assign_codes_uom(cr, registry)
    url = 'http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv33.xsd'
    _load_xsd_files(cr, registry, url)


def _load_product_sat_catalog(cr, registry):
    """Import CSV data as it is faster than xml and because we can't use
    noupdate anymore with csv"""
    csv_path = join(dirname(realpath(__file__)), 'data',
                    'l10n_mx_edi.product.sat.code.csv')
    csv_file = open(csv_path, 'rb')
    cr.copy_expert(
        """COPY l10n_mx_edi_product_sat_code(code, name, applies_to, active)
           FROM STDIN WITH DELIMITER '|'""", csv_file)
    # Create xml_id, to allow make reference to this data
    cr.execute(
        """INSERT INTO ir_model_data
           (name, res_id, module, model)
           SELECT concat('prod_code_sat_', code), id, 'l10n_mx_edi', 'l10n_mx_edi.product.sat.code'
           FROM l10n_mx_edi_product_sat_code """)


def _assign_codes_uom(cr, registry):
    """Assign the codes in UoM of each data, this is here because the data is
    created in the last method"""
    tools.convert.convert_file(
        cr, 'l10n_mx_edi', 'data/product_data.xml', None, mode='init',
        kind='data')


def _load_xsd_files(cr, registry, url):
    fname = url.split('/')[-1]
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        res = objectify.fromstring(response.content)
    except (requests.exceptions.HTTPError, etree.XMLSyntaxError) as e:
        logging.getLogger(__name__).info(
            'I cannot connect with the given URL or you are trying to load an '
            'invalid xsd file.\n%s', e.message)
        return ''
    namespace = {'xs': 'http://www.w3.org/2001/XMLSchema'}
    sub_urls = res.xpath('//xs:import', namespaces=namespace)
    for s_url in sub_urls:
        s_url_catch = _load_xsd_files(cr, registry, s_url.get('schemaLocation'))
        s_url.attrib['schemaLocation'] = s_url_catch
    try:
        xsd_string = etree.tostring(res, pretty_print=True)
    except etree.XMLSyntaxError:
        logging.getLogger(__name__).info('XSD file downloaded is not valid')
        return ''
    env = api.Environment(cr, SUPERUSER_ID, {})
    xsd_fname = 'xsd_cached_%s' % fname.replace('.', '_')
    attachment = env['ir.attachment'].create({
        'name': xsd_fname,
        'datas_fname': fname,
        'datas': base64.encodestring(xsd_string),
    })
    # Forcing the triggering of the store_fname
    attachment._inverse_datas()
    cr.execute(
        """INSERT INTO ir_model_data
           (name, res_id, module, model)
           VALUES (%s, %s, 'l10n_mx_edi', 'ir.attachment')""", (
               xsd_fname, attachment.id))
    filestore = tools.config.filestore(cr.dbname)
    return join(filestore, attachment.store_fname)
