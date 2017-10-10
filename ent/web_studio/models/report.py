# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class Report(models.Model):
    _inherit = 'ir.actions.report'

    @api.model
    def render_qweb_html(self, docids, data=None):
        try:
            return super(Report, self).render_qweb_html(docids, data)
        except UserError as e:
            if not data.get('studio'):
                raise
            _logger.warning("Cannot edit report %r with studio: %s", self.report_name, e)
            return ''
