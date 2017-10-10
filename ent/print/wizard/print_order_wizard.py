# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PrintOrderWizard(models.TransientModel):
    """ This wizard aims to generate the print order relative to the selected 'printable' objects (account.invoice,
        sale.order, ...).
    """

    _name = 'print.order.wizard'
    _description = 'Print Order Wizard'
    _rec_name = 'provider_id'

    @api.model
    def _default_print_provider(self):
        return self.env['ir.default'].get('print.order', 'provider_id')

    @api.model
    def default_get(self, fields):
        result = super(PrintOrderWizard, self).default_get(fields)

        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model', False)
        result['res_model'] = active_model
        # generate line values
        if active_model and active_ids and 'print_order_line_wizard_ids' in fields:
            line_values = []
            for record in self.env[active_model].browse(active_ids):
                line_values.append({
                    'res_id': record.id,
                    'res_name': record.display_name,
                    'res_sendable': record.print_is_sendable,
                    'partner_id': record.partner_id.id if 'partner_id' in record else False,
                    'partner_has_address': record.partner_id.has_address if 'partner_id' in record else False,
                    'last_send_date': record.print_sent_date,
                })
            result['print_order_line_wizard_ids'] = [
                (0, 0, vals) for vals in line_values
            ]
        # add a default report
        if active_model and 'report_id' in fields:
            result['report_id'] = self.env['ir.actions.report'].search([('model', '=', active_model)], limit=1).id
        return result

    ink = fields.Selection([('BW', 'Black & White'), ('CL', 'Colour')], "Ink", default='BW')
    paper_weight = fields.Integer("Paper Weight", default=80, readonly=True)
    provider_id = fields.Many2one('print.provider', 'Print Provider', required=True, default=_default_print_provider)
    provider_balance = fields.Float("Provider Credit", digits=(16, 2), related='provider_id.balance')
    provider_environment = fields.Selection([('test', 'Test'), ('production', 'Production')], "Environment", default=False, related='provider_id.environment')
    provider_currency_id = fields.Many2one('res.currency', 'Currency', related='provider_id.currency_id', oldname="currency_id", readonly=True)
    print_order_line_wizard_ids = fields.One2many('print.order.line.wizard', 'print_order_wizard_id', string='Lines')

    res_model = fields.Char('Resource Model')
    error_message = fields.Text("Error", compute='_compute_error_message')
    report_id = fields.Many2one('ir.actions.report', 'Report', domain=lambda self: [('model', '=', self.env.context.get('active_model'))])

    @api.onchange('provider_id')
    def _onchange_provider_id(self):
        self.provider_currency_id = self.provider_id.currency_id

    @api.one
    @api.depends('print_order_line_wizard_ids')
    def _compute_error_message(self):
        message = False
        unsendable = len(self.print_order_line_wizard_ids.filtered(lambda l: not l.partner_has_address or not l.res_sendable))
        if unsendable:
            if len(self.print_order_line_wizard_ids) == 1:
                message = _("The document you want to send contains a mistake.")
            else:
                message = _("At least one of the document you want to send contains a mistake.")
            message += _("Please check the document is in a correct state, and that its partner has a correct postal address.")
        self.error_message = message

    @api.multi
    def action_apply(self):
        PrintOrder = self.env['print.order']
        for wizard in self:
            # raise UserError if the provider is not configured
            wizard.provider_id.check_configuration()
            # don't do anything if the balance is too small in the production mode (in test mode, allow all)
            wizard.provider_id.check_credit()
            for line in wizard.print_order_line_wizard_ids:
                PrintOrder.create({
                    'ink': wizard.ink,
                    'paper_weight': wizard.paper_weight,
                    'provider_id': wizard.provider_id.id,
                    'currency_id': wizard.provider_currency_id.id,
                    'user_id': self._uid,
                    'res_id': line.res_id,
                    'res_model': line.print_order_wizard_id.res_model,
                    'report_id': wizard.report_id.id,
                    # duplicate partner infos
                    'partner_id': line.partner_id.id,
                    'partner_name': line.partner_id.name,
                    'partner_street': line.partner_id.street,
                    'partner_street2': line.partner_id.street2,
                    'partner_state_id': line.partner_id.state_id.id,
                    'partner_zip': line.partner_id.zip,
                    'partner_city': line.partner_id.city,
                    'partner_country_id': line.partner_id.country_id.id,
                })
        return {'type': 'ir.actions.act_window_close'}


class PrintOrderLineWizard(models.TransientModel):

    _name = 'print.order.line.wizard'
    _rec_name = 'res_name'

    print_order_wizard_id = fields.Many2one('print.order.wizard', 'Print Order Wizard')
    res_id = fields.Integer('Resource ID', readonly=True)
    res_name = fields.Char('Document', readonly=True)
    res_sendable = fields.Boolean('Document sensable', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Recipient partner', readonly=True)
    partner_has_address = fields.Boolean("Partner has an addess", readonly=True)
    last_send_date = fields.Datetime("Last Send Date", readonly=True)
