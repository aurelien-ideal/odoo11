# -*- coding: utf-8 -*-
"""
Website-context rendering needs to add some metadata to rendered fields,
as well as render a few fields differently.

Also, adds methods to convert values back to odoo models.
"""

from odoo import models
from odoo.tools import pycompat


class QWeb(models.AbstractModel):
    """ QWeb object for rendering stuff in the website context
    """
    _inherit = 'ir.qweb'

    def render(self, id_or_xml_id, values=None, **options):
        website_id = self.env.context.get('website_id')
        if website_id:
            if 'experiment_id' in self.env.context:
                #Is there a version which have the view.key == id_or_xml_id and which is in a running experiment?
                exp_version = self.env["website_version.experiment.version"].search([
                    ('version_id.view_ids.key', '=', id_or_xml_id),
                    ('experiment_id.state', '=', 'running'),
                    ('experiment_id.website_id.id', '=', website_id)], limit=1)
                if exp_version:
                    #If yes take the first because there is no overlap between running experiments.
                    exp = exp_version.experiment_id
                    #We set the google_id as key in the dictionnary to avoid problem when reinitializating the db, exp.google_id is unique
                    version_id = self.env.context.get('website_version_experiment').get(str(exp.google_id))
                    if version_id:
                        self.context['version_id'] = int(version_id)

            if isinstance(id_or_xml_id, pycompat.integer_types):
                id_or_xml_id = self.env["ir.ui.view"].browse(id_or_xml_id).key

            domain = [('key', '=', id_or_xml_id), '|', ('website_id', '=', website_id), ('website_id', '=', False)]
            version_id = self.env.context.get('version_id')
            domain += version_id and ['|', ('version_id', '=', False), ('version_id', '=', version_id)] or [('version_id', '=', False)]

            id_or_xml_id = self.env["ir.ui.view"].search(domain, order='website_id, version_id', limit=1).id

        return super(QWeb, self).render(id_or_xml_id, values, **options)
