# -*- coding: utf-8 -*-
from odoo import http


class Database(http.Controller):
    @http.route('/project_timesheet_synchro/timesheet_app', type='http', auth="user")
    def project_timesheet_ui(self, **kw):
        return http.request.render("project_timesheet_synchro.index")
