# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PaymentMethod(models.Model):
    """Added to manage the payment methods from SAT master data.
    Electronic documents need this information from such data.
    Here the `xsd <goo.gl/Vk3IF1>`_
    The payment method is an required attribute, to express the payment method
    of assets or services covered by the voucher.
    It is understood as a payment method legends such as check,
    credit card or debit card, deposit account, etc.
    Note: Odoo have the model payment.method, but this model need fields that
    we not need in this feature as partner_id, acquirer, etc., and they are
    there with other purpose, then a new model is necessary in order to avoid
    lose odoo's features"""

    _name = 'l10n_mx_edi.payment.method'

    name = fields.Char(
        required=True,
        help='Payment method, is found in the SAT catalog.')
    code = fields.Char(
        required=True,
        help='Code defined by the SAT by this payment method. This value will '
        'be set in the XML node "metodoDePago".')
    active = fields.Boolean(
        default=True,
        help='If this payment method is not used by the company could be '
        'deactivated.')
