# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare

# Available values for the release_to_pay field.
_release_to_pay_status_list = [('yes', 'Yes'), ('no', 'No'), ('exception', 'Exception')]

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    release_to_pay = fields.Selection(
        _release_to_pay_status_list,
        compute='_compute_release_to_pay',
        copy=False,
        store=True,
        string='Should be paid',
        help="This field can take the following values :\n"
             "  * Yes: you should pay the bill, you have received the products\n"
             "  * No, you should not pay the bill, you have not received the products\n"
             "  * Exception, there is a difference between received and billed quantities\n"
             "This status is defined automatically, but you can force it by ticking the 'Force Status' checkbox.")
    release_to_pay_manual = fields.Selection(
        _release_to_pay_status_list,
        string='Should be paid',
        help="  * Yes: you should pay the bill, you have received the products\n"
             "  * No, you should not pay the bill, you have not received the products\n"
             "  * Exception, there is a difference between received and billed quantities.")
    force_release_to_pay = fields.Boolean(
        string="Force status",
        help="Indicates whether the 'Can be paid' status is defined automatically or manually.")

    @api.depends('invoice_line_ids.can_be_paid', 'release_to_pay_manual', 'force_release_to_pay')
    def _compute_release_to_pay(self):
        for invoice in self:
            if invoice.force_release_to_pay and invoice.release_to_pay_manual:
                #we must use the manual value contained in release_to_pay_manual
                invoice.release_to_pay = invoice.release_to_pay_manual
            else:
                #otherwise we must compute the field
                result = None
                for invoice_line in invoice.invoice_line_ids:
                    line_status = invoice_line.can_be_paid
                    if line_status == 'exception':
                        #If one line is in exception, the entire bill is
                        result = 'exception'
                        break
                    elif not result:
                        result = line_status
                    elif line_status != result:
                        result = 'exception'
                        break
                    #The last two elif conditions model the fact that a
                    #bill will be in exception if its lines have different status.
                    #Otherwise, its status will be the one all its lines share.

                #'result' can be None if the bill was entirely empty.
                invoice.release_to_pay = result or 'no'


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.depends('purchase_line_id.qty_received', 'purchase_line_id.qty_invoiced', 'purchase_line_id.product_qty')
    def _can_be_paid(self):
        """
        Gives the release_to_pay status of and invoice line.

        Possible return values are
        'yes': the content of the line has been received
        'no' : the content of the line hasn't been received at all
        'exception' : the received quantities and the line's differ
        """

        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for invoice_line in self:
            po_line = invoice_line.purchase_line_id
            if po_line:
                invoiced_qty = po_line.qty_invoiced
                received_qty = po_line.qty_received
                ordered_qty = po_line.product_qty

                if float_compare(invoiced_qty, received_qty, precision_digits=precision) == 0:
                    invoice_line.can_be_paid = 'yes'
                    continue

                if received_qty == 0 and invoiced_qty <= ordered_qty:
                    #"and part" to ensure a too high billed quantity results in an exception:
                    invoice_line.can_be_paid = 'no'
                    continue

                invoice_line.can_be_paid = 'exception'
                continue
            #Serves as default if the line is not linked to any Purchase.
            invoice_line.can_be_paid = 'no'

    can_be_paid = fields.Selection(
        _release_to_pay_status_list,
        compute='_can_be_paid',
        copy=False,
        store=True,
        string='Release to Pay')
