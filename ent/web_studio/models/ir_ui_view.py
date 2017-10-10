# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import difflib
import io
from lxml import etree
from lxml.builder import E
from odoo import models
import json
import uuid

from odoo.tools import pycompat


class View(models.Model):
    _name = 'ir.ui.view'
    _inherit = ['studio.mixin', 'ir.ui.view']

    def _apply_group(self, model, node, modifiers, fields):
        # apply_group only returns the view groups ids.
        # As we need also need their name and display in Studio to edit these groups
        # (many2many widget), they have been added to node (only in Studio).
        if self._context.get('studio'):
            if node.get('groups'):
                studio_groups = []
                for xml_id in node.attrib['groups'].split(','):
                    group = self.env['ir.model.data'].xmlid_to_object(xml_id)
                    if group:
                        studio_groups.append({
                            "id": group.id,
                            "name": group.name,
                            "display_name": group.display_name
                        })
                node.attrib['studio_groups'] = json.dumps(studio_groups)

        return super(View, self)._apply_group(model, node, modifiers, fields)

    def create_simplified_form_view(self, res_model):
        model = self.env[res_model]
        rec_name = model._rec_name_fallback()
        title = etree.fromstring("""
            <div class="oe_title">
                <h1>
                    <field name="%(field_name)s" required="1"/>
                </h1>
            </div>
        """ % {'field_name': rec_name})
        group_name = 'studio_group_' + str(uuid.uuid4())[:6]
        group_1 = E.group(name=group_name + '_left')
        group_2 = E.group(name=group_name + '_right')
        group = E.group(group_1, group_2, name=group_name)
        form = E.form(E.sheet(title, group, string=model._description))
        arch = etree.tostring(form, encoding='unicode', pretty_print=True)

        self.create({
            'type': 'form',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('form', res_model),
        })

    # Returns "true" if the view_id is the id of the studio view.
    def _is_studio_view(self):
        return self.xml_id.startswith('studio_customization')

    # Based on inherit_branding of ir_ui_view
    # This will add recursively the groups ids on the spec node.
    def _groups_branding(self, specs_tree, view_id):
        groups_id = self.browse(view_id).groups_id
        if groups_id:
            attr_value = ','.join(pycompat.imap(str, groups_id.ids))
            for node in specs_tree.iter(tag=etree.Element):
                node.set('studio-view-group-ids', attr_value)

    # Used for studio views only.
    # This studio view specification will not always be available.
    # So, we add the groups name to find out when they will be available.
    # This information will be used in Studio to inform the user.
    def _set_groups_info(self, node, group_ids):
        groups = self.env['res.groups'].browse(pycompat.imap(int, group_ids.split(',')))
        view_group_names = ','.join(groups.mapped('name'))
        for child in node.iter(tag=etree.Element):
            child.set('studio-view-group-names', view_group_names)
            child.set('studio-view-group-ids', group_ids)

    # Used for studio views only.
    # Check if the hook node depends of groups.
    def _check_parent_groups(self, source, spec):
        node = self.locate_node(source, spec)
        if node is not None and node.get('studio-view-group-ids'):
            # Propogate group info for all children
            self._set_groups_info(spec, node.get('studio-view-group-ids'))

    # Used for studio views only.
    # Apply spec by spec studio view.
    def _apply_studio_specs(self, source, specs_tree, studio_view_id):
        for spec in specs_tree.iterchildren(tag=etree.Element):
            if self._context.get('studio'):
                # Detect xpath base on a field added by a view with groups
                self._check_parent_groups(source, spec)
                # Here, we don't want to catch the exception.
                # This mechanism doesn't save the view if something goes wrong.
                source = super(View, self).apply_inheritance_specs(source, spec, studio_view_id)
            else:
                # Avoid traceback if studio view and skip xpath when studio mode is off
                try:
                    source = super(View, self).apply_inheritance_specs(source, spec, studio_view_id)
                except ValueError:
                    # 'locate_node' already log this error.
                    pass
        return source

    def apply_inheritance_specs(self, source, specs_tree, inherit_id):
        # Add branding for groups if studio mode is on
        if self._context.get('studio'):
            self._groups_branding(specs_tree, inherit_id)

        # If this is studio view, we want to apply it spec by spec
        if self.browse(inherit_id)._is_studio_view():
            return self._apply_studio_specs(source, specs_tree, inherit_id)
        else:
            return super(View, self).apply_inheritance_specs(source, specs_tree, inherit_id)

    def locate_node(self, arch, spec):
        # Remove branding added by '_groups_branding'
        spec.attrib.pop("studio-view-group-ids", None)
        return super(View, self).locate_node(arch, spec)

    def normalize(self):
        """
        Normalizes the studio arch by comparing the studio view to the base view
        and combining as many xpaths as possible in order to have a more compact
        final view

        Returns the normalized studio arch
        """
        # Beware ! By its reasoning, this function assumes that the view you
        # want to normalize is the last one to be applied on its root view.
        # This could be improved by deactivating all views that would be applied
        # after this one when calling the read_combined to get the old_view then
        # re-enabling them all afterwards.

        # Fetch the root view
        root_view = self
        while root_view.mode != 'primary':
            root_view = root_view.inherit_id

        parser = etree.XMLParser(remove_blank_text=True)
        new_view = root_view.read_combined()['arch']

        # Get the result of the xpath applications without this view
        self.active = False
        old_view = root_view.read_combined()['arch']
        self.active = True

        # The parent data tag is missing from read_combined
        new_view_tree = etree.Element('data')
        new_view_tree.append(etree.parse(io.StringIO(new_view), parser).getroot())
        old_view_tree = etree.Element('data')
        old_view_tree.append(etree.parse(io.StringIO(old_view), parser).getroot())

        new_view_arch_string = self._stringify_view(new_view_tree)
        old_view_arch_string = self._stringify_view(old_view_tree)

        diff = difflib.ndiff(old_view_arch_string.split('\n'), new_view_arch_string.split('\n'))

        # Format of difflib.ndiff output is:
        #   unchanged
        # - removed
        # + added
        # ? details
        # <empty line after details>
        #   unchanged

        arch = etree.Element('data')
        xpath = etree.Element('xpath')
        old_view_iterator = old_view_tree.getiterator()
        new_view_iterator = new_view_tree.getiterator()
        for line in diff:
            if line.strip() and not line.startswith('?'):  # Ignore details lines
                if line.startswith('-'):
                    node = next(old_view_iterator)

                    # If we are already writing an xpath, we need to either
                    # close it or ignore this line
                    if xpath.attrib.get('expr'):
                        # Maybe we are already removing the parent of this
                        # node so this one will be removed automatically
                        current_xpath_target = old_view_tree.find('.' + xpath.attrib.get('expr'))
                        if xpath.get('position') == 'replace' and \
                                current_xpath_target in node.iterancestors():
                            continue
                        # If we are already adding stuff just before this node,
                        # we could as well replace it directly by what we want to add
                        # Also take care not to close the xpath is we are still
                        # in the attributes section of a given node
                        elif ((node.tag != 'attribute' and xpath.get('position') != 'after') or
                                (node.tag == 'attribute' and xpath.get('position') != 'attributes')):
                            # Consecutive removals need different xpath
                            arch.append(xpath)
                            xpath = etree.Element('xpath')

                    xpath.attrib['expr'] = self._node_to_xpath(node)
                    if node.tag == 'attribute':
                        xpath.attrib['position'] = 'attributes'
                    else:
                        xpath.attrib['position'] = 'replace'

                elif line.startswith('+'):
                    node = next(new_view_iterator)

                    if node.tag == 'attributes':
                        continue

                    # The node for which this is the attribute may have been
                    # added by studio, in which case we don't need a new
                    # xpath to handle it properly
                    if node.tag == 'attribute' and self._get_node_from_xpath(xpath, node.getparent().getparent()) is not None:
                        continue

                    # If the current xpath is not compatible with what we want
                    # to add, we need to close it.
                    if xpath.get('expr') and not self._is_compatible(xpath, node):
                            arch.append(xpath)
                            xpath = etree.Element('xpath')

                    # At this point, we either have no current xpath, or the one
                    # that exists is compatible with what we want to add
                    if not xpath.get('expr'):
                        xpath.attrib['expr'], xpath.attrib['position'] = self._closest_node_to_xpath(node, old_view_tree)

                    # Is your parent a studio node ? If yes, append inside of it
                    parent_node = node.getparent()
                    if parent_node is not None:
                        studio_parent_node = self._get_node_from_xpath(xpath, parent_node)
                    if parent_node is not None and studio_parent_node is not None:
                        self._clone_and_append_to(node, studio_parent_node)
                    else:
                        self._clone_and_append_to(node, xpath)

                else:
                    old_node = next(old_view_iterator)
                    next(new_view_iterator)
                    # This is an unchanged line, if an xpath is ungoing, close it.
                    if old_node.tag not in ['attribute', 'attributes']:
                        if xpath.attrib.get('expr'):
                            arch.append(xpath)
                            xpath = etree.Element('xpath')

        # Append last remaining xpath if needed
        if len(xpath):
            arch.append(xpath)

        normalized_arch = etree.tostring(self._indent_tree(arch), encoding='unicode') if len(arch) else u''
        return normalized_arch

    def _is_compatible(self, xpath, node):
        """
        Check if a node can be merged inside an existing xpath

        Returns True if the node can be fit inside the given xpath, False otherwise
        """
        # Not compatible is either:
        # - position != attributes when node is an attribute
        # - position == attributes when node is not an attribute
        # - the node we want to add is not contiguous with the current xpath,
        #   which means the current xpath is not empty and the node preceding
        #   the one we we want to add is not in the xpath
        if node.tag == 'attribute':
            return xpath.get('position') == 'attributes'
        elif xpath.get('position') == 'attributes':
            return False
        elif not len(xpath):
            return True

        # If the preceding node is in the current xpath, we can append to it
        previous_node = node.getprevious()
        if (previous_node is None or previous_node.tag in ['attribute', 'attributes']):
            previous_node = node.getparent()
            if node.getparent() == 'attributes':
                previous_node = node.getparent()

        return self._get_node_from_xpath(xpath, previous_node) is not None

    def _get_node_from_xpath(self, xpath, node):
        """
        Get a node from within an xpath if it exists

        Returns a node if it exists within the given xpath, None otherwise
        """
        for n in xpath.getiterator():
            if n.tag == node.tag and n.attrib == node.attrib and n.text == node.text:
                return n
        return None

    def _clone_and_append_to(self, node, parent_node):
        """
        Clones the passed-in node and appends it to the passed-in
        parent_node

        Returns the parent_node with the newly-appended node
        """
        if node.tag is etree.Comment:
            # For comments, node.tag is the constructor of Comment nodes
            elem = parent_node.append(etree.Comment(node.text))
        else:
            # This doesn't copy the children, but we don't truly
            # care, since children will be another diff line
            elem = etree.SubElement(parent_node, node.tag, node.attrib)
            elem.text = node.text
            elem.tail = node.tail
        return elem

    def _node_to_xpath(self, target_node):
        """
        Creates and returns a relative xpath that points to target_node
        """
        if target_node.tag == 'attribute':
            target_node = target_node.getparent().getparent()

        if target_node.attrib.get('name'):
            expr = '//%s' % self._identify_node(target_node)

        else:
            ancestors = [
                self._identify_node(n)
                for n in target_node.iterancestors()
                if n.getparent() is not None
            ]
            expr = '//%s/%s' % ('/'.join(reversed(ancestors)), self._identify_node(target_node))

        return expr

    def _identify_node(self, node):
        """
        Creates and returns an identifier for the passed-in node either by using
        its name attribute (relative identifier) or by getting the number of preceding
        sibling elements (absolute identifier)
        """
        if node.get('name'):
            node_str = '%s[@name=\'%s\']' % (node.tag, node.get('name'))
        else:
            node_str = '%s[%s]' % (
                node.tag,
                len(list(node.itersiblings(tag=node.tag, preceding=True))) + 1
            )
        return node_str

    def _closest_node_to_xpath(self, node, old_view):
        """
        Returns an expr and position for the node closest to the passed-in node so
        that it may be used as a target.

        The closest node will be one adjacent to this one and that has an identifiable
        name (name attr), this can be it's next sibling, previous sibling or its parent.

        If none is found, the method will fallback to next/previous sibling or parent even if they
        don't have an identifiable name, in which case an absolute xpath expr will be generated
        """
        def _is_valid_anchor(target_node):
            if (target_node is None) or (target_node.tag in ['attribute', 'attributes']):
                return None
            target_node_expr = '.' + self._node_to_xpath(target_node)
            return old_view.find(target_node_expr) is not None

        nxt = node.getnext()
        prev = node.getprevious()

        if node.tag == 'attribute':
            # Invisible element
            target_node = node.getparent().getparent()  # /node/attributes/attribute
            reanchor_position = 'attributes'
        else:
            # Visible element
            while prev is not None or nxt is not None:
                # Try to anchor onto the closest adjacent element
                if _is_valid_anchor(prev):
                    target_node = prev
                    reanchor_position = 'after'
                    break
                elif _is_valid_anchor(nxt):
                    target_node = nxt
                    reanchor_position = 'before'
                    break
                else:
                    if prev is not None:
                        prev = prev.getprevious()
                    if nxt is not None:
                        nxt = nxt.getnext()
            else:
                # Reanchor on first parent, but the "inside" will make it last child
                target_node = node.getparent()
                reanchor_position = 'inside'

        reanchor_expr = self._node_to_xpath(target_node)
        return reanchor_expr, reanchor_position

    def _stringify_view(self, arch):
        return self._stringify_node('', arch)

    def _stringify_node(self, ancestor, node):
        """
        Converts a node into its string representation

        Example:
            from: <field name='color'/>
              to: "/field[@name='color']\n"

        Returns the stringified node
        """
        result = ''
        node_string = ancestor + '/'
        if node.tag is etree.Comment:
            node_string += 'comment'
        else:
            node_string += node.tag

        if node.get('name') and node.get('name').strip():
            node_string += '[@name=%s]' % node.get('name').strip().replace('\n', ' ')
        if node.text and node.text.strip():
            node_string += '[@text=%s]' % node.text.strip().replace('\n', ' ')
        if node.tail and node.tail.strip():
            node_string += '[@tail=%s]' % node.tail.strip().replace('\n', ' ')
        result += node_string + '\n'

        self._generate_node_attributes(node)
        for child in node.iterchildren():
            result += self._stringify_node(node_string, child)

        return result

    def _generate_node_attributes(self, node):
        """
        Generates an attributes element with all of the node's
        attributes and inserts it as its first child of the node
        """
        if node.tag != 'attribute':
            # node.items() gives a list of tuples, each tuple representing
            # a key, value pair for attributes
            node_attributes = sorted(node.items(), key=lambda i: i[0])  # alphabetically sort attributes by name
            if len(node_attributes):
                attributes = etree.Element('attributes')
                for attr in node_attributes:
                    etree.SubElement(attributes, 'attribute', {
                        'name': attr[0],
                    }).text = attr[1]
                node.insert(0, attributes)

    def _indent_tree(self, elem, level=0):
        """
        The lxml library doesn't pretty_print xml tails, this method aims
        to solve this.

        Returns the elem with properly indented text and tail
        """
        # See: http://lxml.de/FAQ.html#why-doesn-t-the-pretty-print-option-reformat-my-xml-output
        # Below code is inspired by http://effbot.org/zone/element-lib.htm#prettyprint
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for subelem in elem:
                self._indent_tree(subelem, level + 1)
            if not subelem.tail or not subelem.tail.strip():
                subelem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
        return elem
