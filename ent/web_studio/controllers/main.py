# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree
from odoo import http, models, _
from odoo.http import content_disposition, request
from odoo.exceptions import UserError, AccessError
from odoo.addons.web_studio.controllers import export

from odoo.tools import ustr


class WebStudioController(http.Controller):

    @http.route('/web_studio/init', type='json', auth='user')
    def studio_init(self):
        return {
            'dbuuid': request.env['ir.config_parameter'].sudo().get_param('database.uuid'),
            'multi_lang': bool(request.env['res.lang'].search_count([('code', '!=', 'en_US')])),
        }

    @http.route('/web_studio/chatter_allowed', type='json', auth='user')
    def is_chatter_allowed(self, model):
        """ Returns True iff a chatter can be activated on the model's form views, i.e. if
            - it is a custom model (since we can make it inherit from mail.thread), or
            - it already inherits from mail.thread.
        """
        Model = request.env[model]
        return Model._custom or isinstance(Model, type(request.env['mail.thread']))

    @http.route('/web_studio/get_studio_action', type='json', auth='user')
    def get_studio_action(self, action_name, model, view_id=None, view_type=None):
        view_type = 'tree' if view_type == 'list' else view_type  # list is stored as tree in db
        model = request.env['ir.model'].search([('model', '=', model)], limit=1)

        action = None
        if hasattr(self, '_get_studio_action_' + action_name):
            action = getattr(self, '_get_studio_action_' + action_name)(model, view_id=view_id, view_type=view_type)

        return action

    def _get_studio_action_acl(self, model, **kwargs):
        return {
            'name': _('Access Control Lists'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.model.access',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {
                'default_model_id': model.id,
                'search_default_model_id': model.id,
            },
            'help': """ <p class="oe_view_nocontent_create">
                Click to add a new access control list.
            </p>
            """,
        }

    def _get_studio_action_automations(self, model, **kwargs):
        return {
            'name': _('Automated Actions'),
            'type': 'ir.actions.act_window',
            'res_model': 'base.automation',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {
                'default_model_id': model.id,
                'search_default_model_id': model.id,
            },
            'help': """ <p class="oe_view_nocontent_create">
                Click to add a new automated action.
            </p>
            """,
        }

    def _get_studio_action_filters(self, model, **kwargs):
        return {
            'name': _('Filter Rules'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.filters',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {  # model_id is a Selection on ir.filters
                'default_model_id': model.model,
                'search_default_model_id': model.model,
            },
            'help': """ <p class="oe_view_nocontent_create">
                Click to add a new filter.
            </p>
            """,
        }

    def _get_studio_action_reports(self, model, **kwargs):
        return {
            'name': _('Reports'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.actions.report',
            'views': [[False, 'kanban'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {
                'default_model': model.model,
                'search_default_model': model.model,
            },
            'help': """ <p class="oe_view_nocontent">
                Click to add a new report.
            </p>
            """,
        }

    def _get_studio_action_translations(self, model, **kwargs):
        """ Open a view for translating the field(s) of the record (model, id). """
        domain = ['|', ('name', '=', model.model), ('name', 'ilike', model.model + ',')]

        # search view + its inheritancies
        views = request.env['ir.ui.view'].search([('model', '=', model.model)])
        domain = ['|', '&', ('name', '=', 'ir.ui.view,arch_db'), ('res_id', 'in', views.ids)] + domain

        def make_domain(fld, rec):
            name = "%s,%s" % (fld.model_name, fld.name)
            return ['&', ('res_id', '=', rec.id), ('name', '=', name)]

        def insert_missing(fld, rec):
            if not fld.translate:
                return []

            if fld.related:
                try:
                    # traverse related fields up to their data source
                    while fld.related:
                        rec, fld = fld.traverse_related(rec)
                    if rec:
                        return ['|'] + domain + make_domain(fld, rec)
                except AccessError:
                    return []

            assert fld.translate and rec._name == fld.model_name
            request.env['ir.translation'].insert_missing(fld, rec)
            return []

        # insert missing translations of views
        for view in views:
            for name, fld in view._fields.items():
                domain += insert_missing(fld, view)

        # insert missing translations of model, and extend domain for related fields
        record = request.env[model.model].search([], limit=1)
        if record:
            for name, fld in record._fields.items():
                domain += insert_missing(fld, record)

        action = {
            'name': _('Translate view'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.translation',
            'view_mode': 'tree',
            'views': [[request.env.ref('base.view_translation_dialog_tree').id, 'list']],
            'target': 'current',
            'domain': domain,
        }

        return action

    @http.route('/web_studio/create_new_menu', type='json', auth='user')
    def create_new_menu(self, app_name=False, menu_name=False, model_id=False, is_app=False, parent_id=None, icon=None):
        """ Create a new menu @menu_name, linked to a new action associated to the model_id
            @param model_id: if not set, the action associated to this menu is the appswitcher
                except if @is_app is True that will create a new model
            @param is_app: if True, create an extra menu (app, without parent)
            @param parent_id: the parent of the new menu.
                To be set if is_app is False.
            @param icon: the icon of the new app.
                It can either be:
                 - the ir.attachment id of the uploaded image
                 - if the icon has been created, an array containing: [icon_class, color, background_color]
                To be set if is_app is True.
        """
        model = None
        if model_id:
            model = request.env['ir.model'].browse(model_id)
        elif is_app:
            # create a new model
            model = request.env['ir.model'].studio_name_create(menu_name)

        # create the action
        if model:
            action = request.env['ir.actions.act_window'].create({
                'name': menu_name,
                'res_model': model.model,
                'help': """
                    <p>
                        This is your new action ; by default, it contains a list view and a form view.
                    </p>
                    <p>
                        You can start customizing these screens by clicking on the Studio icon on the
                        top right corner (you can also customize this help message there).
                    </p>
                """,
            })
            action_ref = 'ir.actions.act_window,' + str(action.id)
        else:
            action = request.env.ref('base.action_open_website')
            action_ref = 'ir.actions.act_url,' + str(action.id)

        if is_app:
            # create the menus (app menu + first submenu)
            menu_values = {
                'name': app_name,
                'child_id': [(0, 0, {
                    'name': menu_name,
                    'action': action_ref,
                })]
            }

            # set icon related fields (depending on the @icon received)
            if isinstance(icon, int):
                icon_id = request.env['ir.attachment'].browse(icon)
                if not icon_id:
                    raise UserError(_('The icon is not linked to an attachment'))
                menu_values['web_icon_data'] = icon_id.datas
            elif isinstance(icon, list) and len(icon) == 3:
                menu_values['web_icon'] = ','.join(icon)
            else:
                raise UserError(_('The icon has not a correct format'))

            new_context = dict(request.context)
            new_context.update({'ir.ui.menu.full_list': True})  # allows to create a menu without action
            new_menu = request.env['ir.ui.menu'].with_context(new_context).create(menu_values)

        else:
            # create the submenu
            new_menu = request.env['ir.ui.menu'].create({
                'name': menu_name,
                'action': action_ref,
                'parent_id': parent_id,
            })

        return {
            'menu_id': new_menu.id,
            'action_id': action.id,
        }

    def create_blank_report(self):
        arch = etree.fromstring("""
            <t t-name="report_blank">
                <t t-call="web.html_container">
                    <t t-foreach="docs" t-as="doc">
                        <t t-call="web.external_layout">
                            <div class="page"/>
                        </t>
                    </t>
                </t>
            </t>
        """)
        return etree.tostring(arch, encoding='utf-8', pretty_print=True)

    def create_business_report(self, model_name):
        def add_column_field(arch, hook, index, one2many_field_id):
            added_nodes_in_table[hook] = True
            column_tr_node_th = arch.find(".//table/thead/tr[1]/th[" + str(index) + "]")
            column_tr_node_th.text = one2many_field_id.field_description
            column_tr_node_td = arch.find(".//table/tbody/tr[1]/td[" + str(index) + "]")
            column_tr_node_td_content = etree.fromstring("""
                <span><t t-esc="line.%(field_name)s"/></span>
            """ % {'field_name': one2many_field_id.name})
            etree_remove_content_node(column_tr_node_td)
            column_tr_node_td.append(column_tr_node_td_content)

        def etree_remove_content_node(node_element):
            node_element.text = None
            for child in list(node_element):
                node_element.remove(child)

        mail_thread_fields = list(request.env['mail.thread'].fields_get())
        mail_activity_mixin_fields = list(request.env['mail.activity.mixin'].fields_get())
        whitelisted_fields = models.MAGIC_COLUMNS + ['display_name']
        blacklisted_fields = set(mail_thread_fields + mail_activity_mixin_fields + ['__last_update']) - set(whitelisted_fields)

        # Create view
        arch = etree.fromstring("""
            <t t-name="web_studio.report_business">
                <t t-call="web.html_container">
                    <t t-foreach="docs" t-as="doc">
                        <t t-call="web.external_layout">
                            <div class="page">
                                <div class="row">
                                    <div name="address" class="col-xs-5 col-xs-offset-7"/>
                                </div>
                                <h2 name="title"/>
                                <div class="row mt32 mb32">
                                    <div name="date" class="col-xs-3">
                                        <strong>Subtitle 1:</strong>
                                    </div>
                                </div>
                                <table class="table table-condensed">
                                    <thead>
                                        <tr>
                                            <th/>
                                            <th class="text-right"/>
                                            <th class="text-right"/>
                                            <th class="text-right"/>
                                            <th class="text-right"/>
                                        </tr>
                                    </thead>
                                    <tbody class="lines_tbody">
                                        <tr t-foreach="range(0, 3)" t-as="line">
                                            <td></td>
                                            <td class="text-right"></td>
                                            <td class="text-right"></td>
                                            <td class="text-right"></td>
                                            <td class="text-right"></td>
                                        </tr>
                                    </tbody>
                                </table>

                                <p name="note">
                                    <strong>Note:</strong>
                                </p>
                            </div>
                        </t>
                    </t>
                </t>
            </t>
        """)

        added_nodes = {
            'address': False,
            'title': False,
            'date': False,
            'table': False,
            'note': False,
        }
        fields = request.env[model_name].fields_get()
        for field_name in fields:
            field_id = request.env['ir.model.fields'].search([('model', '=', model_name), ('name', '=', field_name)])
            if field_id.name not in blacklisted_fields:
                if not added_nodes['address'] and field_id.ttype == 'many2one' and field_id.relation == 'res.partner':
                    added_nodes['address'] = True
                    # Add address
                    address_node = etree.fromstring("""
                        <div t-field="doc.%(field_name_address)s" t-options='{"widget": "contact", "fields": ["address", "name"], "no_marker": True}'/>
                    """ % {'field_name_address': field_id.name})
                    arch.find(".//div[@name='address']").append(address_node)
                elif not added_nodes['title'] and field_id.name in ['name', 'x_name']:
                    added_nodes['title'] = True
                    # Add title
                    title_node = etree.fromstring("""
                        <strong><t t-esc="doc.%(field_name_title)s"/></strong>
                    """ % {'field_name_title': field_id.name})
                    arch.find(".//h2[@name='title']").append(title_node)
                elif not added_nodes['date'] and field_id.ttype in ['date', 'datetime']:
                    added_nodes['date'] = True
                    # Add date
                    old_date_node = arch.find(".//div[@name='date']")
                    etree_remove_content_node(old_date_node)
                    etree.SubElement(old_date_node, 'strong').text = field_id.field_description
                    etree.SubElement(old_date_node, 'p').append(
                        etree.Element('t', {'t-esc': 'doc.' + field_id.name})
                    )
                elif not added_nodes['note'] and field_id.ttype == 'html':
                    added_nodes['note'] = True
                    # Add note
                    date_node = etree.fromstring("""
                        <strong>Note: <t t-esc="doc.%(field_name_note)s"/></strong>
                    """ % {'field_name_note': field_id.name})
                    old_note_node = arch.find(".//p[@name='note']")
                    etree_remove_content_node(old_note_node)
                    old_note_node.append(date_node)
                elif not added_nodes['table'] and field_id.ttype == 'one2many':
                    added_nodes['table'] = True
                    added_nodes_in_table = {
                        'name': False,
                        'description': False,
                        'quantity': False,
                        'price': False,
                        'total': False,
                    }
                    one2many_fields = request.env[field_id.relation].fields_get()
                    for one2many_field in one2many_fields:
                        one2many_field_id = request.env['ir.model.fields'].search([('model', '=', field_id.relation), ('name', '=', one2many_field)])
                        if one2many_field_id.name not in blacklisted_fields:
                            # Edit table
                            column_1_tr_node_tbody = arch.find(".//table/tbody/tr[1]")
                            column_1_tr_node_tbody.attrib['t-foreach'] = 'doc.' + field_id.name
                            if not added_nodes_in_table['name'] and one2many_field_id.ttype == 'char':
                                add_column_field(arch, 'name', 1, one2many_field_id)
                            elif not added_nodes_in_table['description'] and one2many_field_id.ttype == 'text':
                                add_column_field(arch, 'description', 2, one2many_field_id)
                            elif not added_nodes_in_table['quantity'] and one2many_field_id.ttype in ['integer', 'float']:
                                add_column_field(arch, 'quantity', 3, one2many_field_id)
                            elif not added_nodes_in_table['price'] and one2many_field_id.ttype == 'float':
                                add_column_field(arch, 'price', 4, one2many_field_id)
                            elif not added_nodes_in_table['total'] and one2many_field_id.ttype == 'monetary':
                                add_column_field(arch, 'total', 5, one2many_field_id)
        return etree.tostring(arch, encoding='utf-8', pretty_print=True)

    @http.route('/web_studio/create_new_report', type='json', auth='user')
    def create_new_report(self, model_name, template_name):
        model = request.env['ir.model'].search([('model', '=', model_name)])

        if template_name == 'report_business':
            arch = self.create_business_report(model.model)
        else:
            arch = self.create_blank_report()

        view = request.env['ir.ui.view'].create({
            'name': 'report',
            'type': 'qweb',
            'arch': arch,
        })
        # FIXME: When website is installed, we need to set key as xmlid to search on a valid domain
        # See '_view_obj' in 'website/model/ir.ui.view'
        new_view_xml_id = view.get_external_id()[view.id]
        view.name = new_view_xml_id
        view.key = new_view_xml_id
        # Create report
        report = request.env['ir.actions.report'].create({
            'name': _('%s Report' % (model.name)),
            'model': model.model,
            'report_type': 'qweb-pdf',
            'report_name': view.name,
        })
        # Add in the print menu (ir_values_id field)
        report.create_action()

        return {
            'id': report.id,
        }

    @http.route('/web_studio/set_background_image', type='json', auth='user')
    def set_background_image(self, attachment_id):
        attachment = request.env['ir.attachment'].browse(attachment_id)
        if attachment:
            request.env.user.sudo(request.uid).company_id.background_image = attachment.datas

    def create_new_field(self, values):
        """ Create a new field with given values.
            In some cases we have to convert "id" to "name" or "name" to "id"
            - "model" is the current model we are working on. In js, we only have his name.
              but we need his id to create the field of this model.
            - The relational widget doesn't provide any name, we only have the id of the record.
              This is why we need to search the name depending of the given id.
        """
        # Get current model
        model = request.env['ir.model'].search([('model', '=', values.pop('model_name'))])
        values['model_id'] = model.id
        # For many2one and many2many fields
        if values.get('relation_id'):
            values['relation'] = request.env['ir.model'].browse(values.pop('relation_id')).model
        # For one2many fields
        if values.get('relation_field_id'):
            field = request.env['ir.model.fields'].browse(values['relation_field_id'])
            values.update(
                relation=field.model_id.model,
                relation_field=field.name,
            )
        if values.get('selection'):
            values['selection'] = ustr(values['selection'])
        # Create new field
        return request.env['ir.model.fields'].create(values)

    @http.route('/web_studio/add_view_type', type='json', auth='user')
    def add_view_type(self, action_type, action_id, res_model, view_type, args):
        view_type = 'tree' if view_type == 'list' else view_type  # list is stored as tree in db
        try:
            request.env[res_model].fields_view_get(view_type=view_type)
        except UserError as e:
            return e.name
        self.edit_action(action_type, action_id, args)
        return True

    @http.route('/web_studio/edit_action', type='json', auth='user')
    def edit_action(self, action_type, action_id, args):

        action_id = request.env[action_type].browse(action_id)
        if action_id:

            if 'groups_id' in args:
                args['groups_id'] = [(6, 0, args['groups_id'])]

            if 'view_mode' in args:
                args['view_mode'] = args['view_mode'].replace('list', 'tree')  # list is stored as tree in db

                # As view_ids has precedence on view_mode, we need to use them and resequence them
                view_modes = args['view_mode'].split(',')
                if action_id.view_ids:
                    missing_view_modes = [x for x in view_modes if x not in [y.view_mode for y in action_id.view_ids]]
                    for view_mode in missing_view_modes:
                        request.env['ir.actions.act_window.view'].create({'view_mode': view_mode, 'act_window_id': action_id.id})
                for view_id in action_id.view_ids:
                    if view_id.view_mode in view_modes:
                        view_id.sequence = view_modes.index(view_id.view_mode)
                    else:
                        view_id.unlink()

            action_id.write(args)

        return True

    @http.route('/web_studio/set_another_view', type='json', auth='user')
    def set_another_view(self, action_id, view_mode, view_id):

        action_id = request.env['ir.actions.act_window'].browse(action_id)
        window_view = request.env['ir.actions.act_window.view'].search([('view_mode', '=', view_mode), ('act_window_id', '=', action_id.id)])
        if not window_view:
            window_view = request.env['ir.actions.act_window.view'].create({'view_mode': view_mode, 'act_window_id': action_id.id})

        window_view.view_id = view_id

        return True

    def _get_studio_view(self, view):
        domain = [('inherit_id', '=', view.id), ('name', '=', self._generate_studio_view_name(view))]
        return view.search(domain, order='priority desc, name desc, id desc', limit=1)

    def _set_studio_view(self, view, arch):
        studio_view = self._get_studio_view(view)
        if studio_view and len(arch):
            studio_view.arch_db = arch
        elif studio_view:
            studio_view.unlink()
        elif len(arch):
            self._create_studio_view(view, arch)

    def _generate_studio_view_name(self, view):
        return "Odoo Studio: %s customization" % (view.name)

    @http.route('/web_studio/get_studio_view_arch', type='json', auth='user')
    def get_studio_view_arch(self, model, view_type, view_id=False):
        view_type = 'tree' if view_type == 'list' else view_type  # list is stored as tree in db

        if not view_id:
            # TOFIX: it's possibly not the used view ; see fields_get_view
            # try to find the lowest priority matching ir.ui.view
            view_id = request.env['ir.ui.view'].default_view(request.env[model]._name, view_type)
        # We have to create a view with the default view if we want to customize it.
        view = self._get_or_create_default_view(model, view_type, view_id)
        studio_view = self._get_studio_view(view)

        return {
            'studio_view_id': studio_view and studio_view.id or False,
            'studio_view_arch': studio_view and studio_view.arch_db or "<data/>",
        }

    @http.route('/web_studio/edit_view', type='json', auth='user')
    def edit_view(self, view_id, studio_view_arch, operations=None):
        IrModelFields = request.env['ir.model.fields']
        view = request.env['ir.ui.view'].browse(view_id)
        field_created = False

        parser = etree.XMLParser(remove_blank_text=True)
        arch = etree.fromstring(studio_view_arch, parser=parser)
        model = view.model
        for op in operations:
            # create a new field if it does not exist
            if 'node' in op:
                if op['node'].get('tag') == 'field' and op['node'].get('field_description'):
                    model = op['node']['field_description']['model_name']
                    # Check if field exists before creation
                    field = IrModelFields.search([
                        ('name', '=', op['node']['field_description']['name']),
                        ('model', '=', model),
                    ], limit=1)
                    if not field:
                        field = self.create_new_field(op['node']['field_description'])
                        field_created = True
                    op['node']['attrs']['name'] = field.name
                if op['node'].get('tag') == 'filter' and op['target']['tag'] == 'group' and op['node']['attrs'].get('create_group'):
                    op['node']['attrs'].pop('create_group')
                    create_group_op = {
                        'node': {
                            'tag': 'group',
                            'attrs': {
                                'name': 'studio_group_by',
                            }
                        },
                        'empty': True,
                        'target': {
                            'tag': 'search',
                        },
                        'position': 'inside',
                    }
                    self._operation_add(arch, create_group_op, model)
            # set a more specific xpath (with templates//) for the kanban view
            if view.type == 'kanban':
                if op.get('target') and op['target'].get('tag') == 'field':
                    op['target']['tag'] = 'templates//field'

            # call the right operation handler
            getattr(self, '_operation_%s' % (op['type']))(arch, op, model)

        # Save or create changes into studio view, identifiable by xmlid
        # Example for view id 42 of model crm.lead: web-studio_crm.lead-42
        new_arch = etree.tostring(arch, encoding='unicode', pretty_print=True)
        self._set_studio_view(view, new_arch)

        # Normalize the view
        studio_view = self._get_studio_view(view)
        ViewModel = request.env[view.model]
        try:
            normalized_view = studio_view.normalize()
            self._set_studio_view(view, normalized_view)
            fields_view = ViewModel.with_context({'studio': True}).fields_view_get(view.id, view.type)
        except ValueError:  # Element '<...>' cannot be located in parent view
            # If the studio view is not applicable after normalization, let's
            # just ignore the normalization step, it's better to have a studio
            # view that is not optimized than to prevent the user from making
            # the change he would like to make.
            self._set_studio_view(view, new_arch)
            fields_view = ViewModel.with_context({'studio': True}).fields_view_get(view.id, view.type)

        view_type = 'list' if view.type == 'tree' else view.type
        result = {'fields_views': {view_type: fields_view}}

        if field_created:
            result['fields'] = ViewModel.fields_get()

        return result

    def _create_studio_view(self, view, arch):
        # We have to play with priorities. Consider the following:
        # View Base: <field name="x"/><field name="y"/>
        # View Standard inherits Base: <field name="x" position="after"><field name="z"/></field>
        # View Custo inherits Base: <field name="x" position="after"><field name="x2"/></field>
        # We want x,x2,z,y, because that's what we did in studio, but the order of xpath
        # resolution is sequence,name, not sequence,id. Because "Custo" < "Standard", it
        # would first resolve in x,x2,y, then resolve "Standard" with x,z,x2,y as result.
        return request.env['ir.ui.view'].create({
            'type': view.type,
            'model': view.model,
            'inherit_id': view.id,
            'mode': 'extension',
            'priority': 99,
            'arch': arch,
            'name': self._generate_studio_view_name(view),
        })

    @http.route('/web_studio/edit_report', type='json', auth='user')
    def edit_report(self, report_id, values):
        report = request.env['ir.actions.report'].browse(report_id)
        if report:
            if 'groups_id' in values:
                values['groups_id'] = [(6, 0, values['groups_id'])]
            report.write(values)

    @http.route('/web_studio/edit_view_arch', type='json', auth='user')
    def edit_view_arch(self, view_id, view_arch):
        view = request.env['ir.ui.view'].browse(view_id)

        if view:
            view.write({'arch': view_arch})

            if view.model:
                ViewModel = request.env[view.model]
                try:
                    fields_view = ViewModel.with_context({'studio': True}).fields_view_get(view.id, view.type)
                    view_type = 'list' if view.type == 'tree' else view.type
                    return {
                        'fields_views': {
                            view_type: fields_view,
                        },
                        'fields': ViewModel.fields_get(),
                    }
                except Exception:
                    return False

    @http.route('/web_studio/export', type='http', auth='user')
    def export(self, token):
        """ Exports a zip file containing the 'studio_customization' module
            gathering all customizations done with Studio (customizations of
            existing apps and freshly created apps).
        """
        studio_module = request.env['ir.module.module'].get_studio_module()
        data = request.env['ir.model.data'].search([('studio', '=', True)])
        content = export.generate_archive(studio_module, data)

        return request.make_response(content, headers=[
            ('Content-Disposition', content_disposition('customizations.zip')),
            ('Content-Type', 'application/zip'),
            ('Content-Length', len(content)),
        ], cookies={'fileToken': token})

    @http.route('/web_studio/create_default_view', type='json', auth='user')
    def create_default_view(self, model, view_type, attrs):
        attrs['string'] = "Default %s view for %s" % (view_type, model)
        # The grid view arch has the attributes set as children nodes and not in
        # the view node
        if view_type == 'grid':
            arch = self._get_default_grid_view(attrs)
        else:
            arch = self._get_default_view(view_type, attrs)
        request.env['ir.ui.view'].create({
            'type': view_type,
            'model': model,
            'arch': arch,
            'name': attrs['string'],
        })

    def _get_default_view(self, view_type, attrs):
        arch = etree.Element(view_type, attrs)
        return etree.tostring(arch, encoding='unicode', pretty_print=True, method='html')

    def _get_or_create_default_view(self, model, view_type, view_id=False):
        View = request.env['ir.ui.view']
        # If we have no view_id to inherit from, it's because we are adding
        # fields to the default view of a new model. We will materialize the
        # default view as a true view so we can keep using our xpath mechanism.
        if view_id:
            view = View.browse(view_id)
        else:
            arch = request.env[model].fields_view_get(view_id, view_type)['arch']
            view = View.create({
                'type': view_type,
                'model': model,
                'arch': arch,
                'name': "Default %s view for %s" % (view_type, model),
            })
        return view

    def _node_to_expr(self, node):
        if not node.get('attrs') and node.get('xpath_info'):
            # Format of expr is /form/tag1[]/tag2[]/[...]/tag[]
            expr = ''.join(['/%s[%s]' % (parent['tag'], parent['indice']) for parent in node.get('xpath_info')])
        else:
            # Format of expr is //tag[@attr1_name=attr1_value][@attr2_name=attr2_value][...]
            expr = '//' + node['tag']
            for k, v in node.get('attrs', {}).items():
                if k == 'class':
                    # Special case for classes which usually contain multiple values
                    expr += '[contains(@%s,\'%s\')]' % (k, v)
                else:
                    expr += '[@%s=\'%s\']' % (k, v)

            # Avoid matching nodes in sub views.
            # Example with field as node:
            # A field should be defined only once in a view but in some cases,
            # a view can be composed by some other views where a field with
            # the same name may exist.
            # Here, we want to generate xpath based on the nodes in the parent view only.
            if not node.get('subview_xpath'):
                expr = expr + '[not(ancestor::field)]'

        # Special case when we have <label/><div/> instead of <field>
        # TODO: This is very naive, couldn't the js detect such a situation and
        #       tell us to anchor the xpath on another element ?
        if node['tag'] == 'label':
            expr = expr + '/following-sibling::div'
        # If we receive a more specific xpath because we are editing an inline
        # view, we add it in front of the generated xpath.
        if node.get('subview_xpath'):
            xpath = node.get('subview_xpath')
            if node.get('isSubviewAttr'):
                expr = xpath
            # Hack to check if the last subview xpath element is not the same than expr
            # E.g when we add a field in an empty subview list the expr computed
            # by studio will be only '/tree' but this is useless since the
            # subview xpath already specify this element. So in this case,
            # we don't add the expr computed by studio.
            elif len(xpath) - len(expr) != xpath.find(expr):
                expr = xpath + expr
        return expr

    # Create a new xpath node based on an operation
    # TODO: rename it in master
    def _get_xpath_node(self, arch, operation):
        expr = self._node_to_expr(operation['target'])
        position = operation['position']

        return etree.SubElement(arch, 'xpath', {
            'expr': expr,
            'position': position
        })

    def _operation_remove(self, arch, operation, model=None):
        expr = self._node_to_expr(operation['target'])

        # We have to create a brand new xpath to remove this field from the view.
        # TODO: Sometimes, we have to delete more stuff than just a single tag !
        etree.SubElement(arch, 'xpath', {
            'expr': expr,
            'position': 'replace'
        })

    def _operation_add(self, arch, operation, model):
        node = operation['node']
        xpath_node = self._get_xpath_node(arch, operation)

        # Take a xml_node and put columns on it:
        # If the xml_node is not a group, this function will create a group node
        # to add two columns on it.
        def add_columns(xml_node, title=False):
            # Get the random key generated is JS.
            # Expected value: 'studio_<tag_name>_<random_key>
            name = 'studio_group_' + xml_node.get('name').split('_')[2]

            if xml_node.tag != 'group':
                xml_node_group = etree.SubElement(xml_node, 'group', {'name': name})
            else:
                xml_node_group = xml_node

            xml_node_page_right = etree.SubElement(xml_node_group, 'group', {'name': name + '_right'})
            xml_node_page_left = etree.SubElement(xml_node_group, 'group', {'name': name + '_left'})
            if title:
                xml_node_page_right.attrib['string'] = _('Right Title')
                xml_node_page_left.attrib['string'] = _('Left Title')

        # Create the actual node inside the xpath. It needs to be the first
        # child of the xpath to respect the order in which they were added.
        xml_node = etree.Element(node['tag'], node.get('attrs'))
        if node['tag'] == 'notebook':
            name = 'studio_page_' + node['attrs']['name'].split('_')[2]
            xml_node_page = etree.Element('page', {'string': 'New Page', 'name': name})
            add_columns(xml_node_page)
            xml_node.insert(0, xml_node_page)
        elif node['tag'] == 'page':
            add_columns(xml_node)
        elif node['tag'] == 'group':
            if 'empty' not in operation:
                add_columns(xml_node, title=True)
        elif node['tag'] == 'button':
            # To create a stat button, we need
            #   - a many2one field (1) that points to this model
            #   - a field (2) that counts the number of records associated with the current record
            #   - an action to jump in (3) with the many2one field (1) as domain/context
            #
            # (1) [button_field] the many2one field
            # (2) [button_count_field] is a non-stored computed field (to always have the good value in the stat button, if access rights)
            # (3) [button_action] an act_window action to jump in the related model
            button_field = request.env['ir.model.fields'].browse(node['field'])
            button_count_field, button_action = self._get_or_create_fields_for_button(model, button_field, node['string'])

            # the XML looks like <button> <field/> </button : a element `field` needs to be inserted inside the button
            xml_node_field = etree.Element('field', {'widget': 'statinfo', 'name': button_count_field.name, 'string': node['string'] or button_count_field.field_description})
            xml_node.insert(0, xml_node_field)

            xml_node.attrib['type'] = 'action'
            xml_node.attrib['name'] = str(button_action.id)
        else:
            xml_node.text = node.get('text')
        xpath_node.insert(0, xml_node)

    def _get_or_create_fields_for_button(self, model, field, button_name):
        """ Returns the button_count_field and the button_action link to a stat button.
            @param field: a many2one field
        """

        if field.ttype != 'many2one' or field.relation != model:
            raise UserError(_('The related field of a button has to be a many2one to %s.' % model))

        model = request.env['ir.model'].search([('model', '=', model)], limit=1)

        # There is a counter on the button ; as the related field is a many2one, we need
        # to create a new computed field that counts the number of records in the one2many
        button_count_field_name = 'x_%s_count' % field.name
        button_count_field = request.env['ir.model.fields'].search([('name', '=', button_count_field_name), ('model_id', '=', model.id)])
        if not button_count_field:
            compute_function = """
                    results = self.env['%(model)s'].read_group([('%(field)s', 'in', self.ids)], '%(field)s', '%(field)s')
                    dic = {}
                    for x in results: dic[x['%(field)s'][0]] = x['%(field)s_count']
                    for record in self: record['%(count_field)s'] = dic.get(record.id, 0)
                """ % {
                    'model': field.model,
                    'field': field.name,
                    'count_field': button_count_field_name,
                }
            button_count_field = request.env['ir.model.fields'].create({
                'name': button_count_field_name,
                'field_description': '%s count' % field.field_description,
                'model': model.model,
                'model_id': model.id,
                'ttype': 'integer',
                'store': False,
                'compute': compute_function.replace('    ', ''),  # remove indentation for safe_eval
            })

        # The action could already exist but we don't want to recreate one each time
        button_action_domain = "[('%s', '=', active_id)]" % (field.name)
        button_action_context = "{'search_default_%s': active_id,'default_%s': active_id}" % (field.name, field.name)
        button_action = request.env['ir.actions.act_window'].search([
            ('name', '=', button_name), ('res_model', '=', field.model),
            ('domain', '=', button_action_domain), ('context', '=', button_action_context),
        ])
        if not button_action:
            # Link the button with an associated act_window
            button_action = request.env['ir.actions.act_window'].create({
                'name': button_name,
                'res_model': field.model,
                'view_mode': 'tree,form',
                'view_type': 'form',
                'domain': button_action_domain,
                'context': button_action_context,
            })

        return button_count_field, button_action

    def _operation_move(self, arch, operation, model=None):
        self._operation_remove(arch, dict(operation, target=operation['node']))
        self._operation_add(arch, operation)

    # Create or update node for each attribute
    def _operation_attributes(self, arch, operation, model=None):
        ir_model_data = request.env['ir.model.data']
        new_attrs = operation['new_attrs']

        if (new_attrs.get('groups')):
            eval_attr = []
            for many2many_value in new_attrs['groups']:
                group_xmlid = ir_model_data.search([
                    ('model', '=', 'res.groups'),
                    ('res_id', '=', many2many_value)])
                eval_attr.append(group_xmlid.complete_name)
            eval_attr = ",".join(eval_attr)
            new_attrs['groups'] = eval_attr
        else:
            # TOFIX
            new_attrs['groups'] = ''

        xpath_node = self._get_xpath_node(arch, operation)

        for key, new_attr in new_attrs.items():
            xml_node = xpath_node.find('attribute[@name="%s"]' % (key))
            if xml_node is None:
                xml_node = etree.Element('attribute', {'name': key})
                xml_node.text = new_attr
                xpath_node.insert(0, xml_node)
            else:
                xml_node.text = new_attr

            # change the field description when changing the field label (for custom fields)
            if key == 'string' and operation.get('node', {}).get('tag') == 'field':
                field_name = operation.get('node', {}).get('attrs', {}).get('name')
                field_id = request.env['ir.model.fields'].search([('model', '=', model), ('name', '=', field_name)])
                if field_name.startswith('x_') and field_id and field_id.field_description != new_attr:
                    field_id.write({'field_description': new_attr})

    def _operation_buttonbox(self, arch, operation, model=None):
        studio_view_arch = arch  # The actual arch is the studio view arch
        # Get the arch of the form view with inherited views applied
        arch = request.env[model].fields_view_get(view_type='form')['arch']
        parser = etree.XMLParser(remove_blank_text=True)
        arch = etree.fromstring(arch, parser=parser)

        # Create xpath to put the buttonbox as the first child of the sheet
        if arch.find('sheet'):
            sheet_node = arch.find('sheet')
            if list(sheet_node):
                # Check if children exists
                xpath_node = etree.SubElement(studio_view_arch, 'xpath', {
                    'expr': '//sheet/*[1]',
                    'position': 'before'
                })
            else:
                xpath_node = etree.SubElement(studio_view_arch, 'xpath', {
                    'expr': '//sheet',
                    'position': 'inside'
                })
            # Create and insert the buttonbox node inside the xpath node
            buttonbox_node = etree.Element('div', {'name': 'button_box', 'class': 'oe_button_box'})
            xpath_node.append(buttonbox_node)

    def _operation_chatter(self, arch, operation, model=None):
        def _get_remove_field_op(arch, field_name):
            return {
                'type': 'remove',
                'target': {
                    'tag': 'field',
                    'attrs': {
                        'name': field_name,
                    },
                }
            }

        if not self.is_chatter_allowed(operation['model']):
            # Chatter can only be activated form models that (can) inherit from mail.thread
            return

        # From this point, the model is either a custom model or inherits from mail.thread
        model = request.env['ir.model'].search([('model', '=', operation['model'])])
        if model.state == 'manual' and not model.is_mail_thread:
            # Activate mail.thread inheritance on the custom model
            model.write({'is_mail_thread': True})

        # Remove message_ids and message_follower_ids if already defined in form view
        if operation['remove_message_ids']:
            self._operation_remove(arch, _get_remove_field_op(arch, 'message_ids'))
        if operation['remove_follower_ids']:
            self._operation_remove(arch, _get_remove_field_op(arch, 'message_follower_ids'))

        xpath_node = etree.SubElement(arch, 'xpath', {
            'expr': '//sheet',
            'position': 'after',
        })
        chatter_node = etree.Element('div', {'class': 'oe_chatter'})
        thread_node = etree.Element('field', {'name': 'message_ids', 'widget': 'mail_thread'})
        follower_node = etree.Element('field', {'name': 'message_follower_ids', 'widget': 'mail_followers'})
        chatter_node.append(follower_node)
        chatter_node.append(thread_node)
        xpath_node.append(chatter_node)

    def _operation_kanban_dropdown(self, arch, operation, model):
        """ Insert a dropdown and its corresponding needs in an kanban view arch.
            Implied modifications:
                - create an integer field x_color in the model if it doesn't exist
                - add the field x_color in the view
                - add a dropdown section in the view
                - modify the kanban class to use `oe_kanban_color_`
        """
        model_id = request.env['ir.model'].search([('model', '=', model)])
        if not model_id:
            return

        color_field_name = 'x_color'
        if not request.env['ir.model.fields'].search([('model_id', '=', model_id.id), ('name', '=', color_field_name), ('ttype', '=', 'integer')]):
            # create a field if it doesn't exist in the model
            request.env['ir.model.fields'].create({
                'model': model,
                'model_id': model_id.id,
                'name': color_field_name,
                'field_description': 'Color',
                'ttype': 'integer',
            })

        # add the field at the beginning
        etree.SubElement(arch, 'xpath', {
            'expr': 'templates',
            'position': 'before',
        }).append(etree.Element('field', {'name': color_field_name}))

        # add the dropdown before the rest
        dropdown_node = etree.fromstring("""
            <div class="o_dropdown_kanban dropdown">
                <a class="dropdown-toggle btn" data-toggle="dropdown" href="#" >
                    <span class="fa fa-bars fa-lg"/>
                </a>
                <ul class="dropdown-menu" role="menu" aria-labelledby="dLabel">
                    <t t-if="widget.editable"><li><a type="edit">Edit</a></li></t>
                    <t t-if="widget.deletable"><li><a type="delete">Delete</a></li></t>
                    <li><ul class="oe_kanban_colorpicker" data-field="%(field)s"/></li>
                </ul>
            </div>
        """ % {'field': color_field_name})
        etree.SubElement(arch, 'xpath', {
            'expr': '//div/*[1]',
            'position': 'before',
        }).append(dropdown_node)

        # set the corresponding color attribute on the kanban record
        xpath_node = etree.SubElement(arch, 'xpath', {
            'expr': '//div',
            'position': 'attributes',
        })
        xml_node = xpath_node.find('attribute[@name="%s"]' % ('color'))
        if xml_node is None:
            xml_node = etree.Element('attribute', {'name': 'color'})
            xml_node.text = color_field_name
            xpath_node.insert(0, xml_node)
        else:
            xml_node.text = color_field_name

    def _operation_kanban_image(self, arch, operation, model):
        """ Insert a image and its corresponding needs in an kanban view arch
            Implied modifications:
                - add the field in the view
                - add a section (kanban_right) in the view
                - add the field with `kanban_image` in this section
        """
        model_id = request.env['ir.model'].search([('model', '=', model)])
        if not model_id:
            raise UserError(_('The model %s does not exist.' % model))

        if not operation.get('field'):
            raise UserError(_('Please specify a field.'))

        field_id = request.env['ir.model.fields'].search([
            ('model', '=', model),
            ('name', '=', operation['field'])
        ])
        if not field_id:
            raise UserError(_('The field %s does not exist.' % operation['field']))

        # add field at the beginning
        etree.SubElement(arch, 'xpath', {
            'expr': 'templates',
            'position': 'before',
        }).append(etree.Element('field', {'name': field_id.name}))

        # add the image inside the view
        etree.SubElement(arch, 'xpath', {
            'expr': '//div',
            'position': 'inside',
        }).append(
            etree.fromstring("""
                <div class="oe_kanban_bottom_right">
                    <img
                        t-att-src="kanban_image('%(model)s', 'image_small', record.%(field)s.raw_value)"
                        t-att-title="record.%(field)s.value"
                        width="24" height="24" class="oe_kanban_avatar pull-right"
                    />
                </div>
            """ % {'model': field_id.relation, 'field': field_id.name})
        )

    def _operation_kanban_priority(self, arch, operation, model):
        """ Insert a priority and its corresponding needs in an kanban view arch
            Implied modifications:
                - create a selection field x_priority in the model if it doesn't exist
                - add a section (kanban_left) in the view
                - add the field x_priority with the widget priority in this section
        """
        model_id = request.env['ir.model'].search([('model', '=', model)])
        if not model_id:
            raise UserError(_('The model %s does not exist.' % model))

        if operation.get('field'):
            field_id = request.env['ir.model.fields'].search([
                ('model', '=', model),
                ('name', '=', operation['field'])
            ])
            if not field_id:
                raise UserError(_('The field %s does not exist.' % operation['field']))

        else:
            field_id = request.env['ir.model.fields'].search([
                ('model_id', '=', model_id.id),
                ('name', '=', 'x_priority'),
                ('ttype', '=', 'selection')
            ])
            # create a field selection x_priority if it doesn't exist in the model
            if not field_id:
                field_id = request.env['ir.model.fields'].create({
                    'model': model,
                    'model_id': model_id.id,
                    'name': 'x_priority',
                    'field_description': 'Priority',
                    'ttype': 'selection',
                    'selection': "[('0', 'Low'), ('1', 'Normal'), ('2', 'High')]",
                })

        # add priority inside the view
        etree.SubElement(arch, 'xpath', {
            'expr': '//div',
            'position': 'inside',
        }).append(
            etree.fromstring("""
                <div class="oe_kanban_bottom_left">
                    <field name="%s" widget="priority"/>
                </div>
            """ % (field_id.name))
        )

    @http.route('/web_studio/get_email_alias', type='json', auth='user')
    def get_email_alias(self, model_name):
        """ Returns the email alias associated to the model @model_name if both exist
        """
        result = {'alias_domain': request.env['ir.config_parameter'].get_param('mail.catchall.domain')}
        model = request.env['ir.model'].search([('model', '=', model_name)], limit=1)
        if model:
            email_alias = request.env['mail.alias'].search([('alias_model_id', '=', model.id)], limit=1)
            if email_alias:
                result['email_alias'] = email_alias.alias_name
        return result

    @http.route('/web_studio/set_email_alias', type='json', auth='user')
    def set_email_alias(self, model_name, value):
        """ Set the email alias associated to the model @model_name
             - if there is no email alias, it will be created
             - if there is one and the value is empty, it will be unlinked
        """
        model = request.env['ir.model'].search([('model', '=', model_name)], limit=1)
        if model:
            email_alias = request.env['mail.alias'].search([('alias_model_id', '=', model.id)], limit=1)
            if email_alias:
                if value:
                    email_alias.alias_name = value
                else:
                    email_alias.unlink()
            else:
                request.env['mail.alias'].create({
                    'alias_model_id': model.id,
                    'alias_name': value,
                })

    @http.route('/web_studio/get_default_value', type='json', auth='user')
    def get_default_value(self, model_name, field_name):
        """ Return the default value associated to the given field. """
        return {
            'default_value': request.env['ir.default'].get(model_name, field_name, company_id=True)
        }

    @http.route('/web_studio/set_default_value', type='json', auth='user')
    def set_default_value(self, model_name, field_name, value):
        """ Set the default value associated to the given field. """
        request.env['ir.default'].set(model_name, field_name, value, company_id=True)

    @http.route('/web_studio/create_stages_model', type='json', auth='user')
    def create_stages_model(self, model_name):
        """ Create a new model if it does not exist
        """
        stages_model = model_name + '_stage'
        if not model_name.startswith('x_'):
            stages_model = 'x_' + stages_model
        model_id = request.env['ir.model'].search([
            ('model', '=', stages_model),
        ])
        if not model_id:
            model = request.env['ir.model'].search([('model', '=', model_name)])
            model_id = request.env['ir.model'].create({
                'model': stages_model,
                'name': model.name + ' ' + _('stages'),
            })
        return model_id.id

    @http.route('/web_studio/create_inline_view', type='json', auth='user')
    def create_inline_view(self, model, view_id, field_name, subview_type):
        inline_view = request.env[model].load_views([[False, subview_type]])
        view = request.env['ir.ui.view'].browse(view_id)
        studio_view = self._get_studio_view(view)
        if not studio_view:
            studio_view = self._create_studio_view(view, '<data/>')
        parser = etree.XMLParser(remove_blank_text=True)
        arch = etree.fromstring(studio_view.arch_db, parser=parser)
        expr = "//field[@name='%s']" % field_name
        position = 'inside'
        xpath_node = arch.find('xpath[@expr="%s"][@position="%s"]' % (expr, position))
        if xpath_node is None:  # bool(node) == False if node has no children
            xpath_node = etree.SubElement(arch, 'xpath', {
                'expr': expr,
                'position': position
            })
        view_arch = inline_view['fields_views'][subview_type]['arch']
        xml_node = etree.fromstring(view_arch)
        xpath_node.insert(0, xml_node)
        studio_view.arch_db = etree.tostring(arch, encoding='utf-8', pretty_print=True)
        return studio_view.arch_db
