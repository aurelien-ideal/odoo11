import textwrap
from odoo.http import _request_stack
from odoo.tests.common import TransactionCase
from odoo.addons.web_studio.controllers.main import WebStudioController


class TestViewNormalization(TransactionCase):

    def setUp(self):
        super(TestViewNormalization, self).setUp()
        _request_stack.push(self)
        self.base_view = self.env.ref('base.view_partner_form')
        self.view = self.base_view.create({
            'arch_base':
            """
            <form string="Partners">
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="toggle_active" type="object" groups="base.group_no_one" class="oe_stat_button" icon="fa-archive">
                            <field name="active" widget="boolean_button" options="{&quot;terminology&quot;: &quot;archive&quot;}"/>
                        </button>
                    </div>
                    <field name="image" widget="image" class="oe_avatar" options="{&quot;preview_image&quot;: &quot;image_medium&quot;, &quot;size&quot;: [90, 90]}"/>
                    <div class="oe_title">
                        <field name="is_company" invisible="1"/>
                        <field name="company_type" widget="radio" class="oe_edit_only" on_change="on_change_company_type(company_type)" options="{'horizontal': true}"/>
                        <h1>
                            <field name="name" default_focus="1" placeholder="Name" attrs="{'required' : [('type', '=', 'contact')]}"/>
                        </h1>
                        <div class="o_row">
                            <field name="parent_id" placeholder="Company" domain="[('is_company', '=', True)]" context="{'default_is_company': True, 'default_supplier': supplier, 'default_customer': customer}" attrs="{'invisible': [('is_company','=', True),('parent_id', '=', False)]}" on_change="onchange_parent_id(parent_id)"/>
                        </div>
                    </div>

                    <group>
                        <group>
                            <field name="type" attrs="{'invisible': [('parent_id','=', False)]}" groups="base.group_no_one"/>
                            <label for="street" string="Address"/>
                            <div class="o_address_format">
                                <div class="oe_edit_only">
                                    <button name="open_parent" type="object" string="(edit)" class="oe_link" attrs="{'invisible': ['|', ('parent_id', '=', False), ('type', '!=', 'contact')]}"/>
                                </div>

                                <field name="street" placeholder="Street..." class="o_address_street" attrs="{'readonly': [('type', '=', 'contact'),('parent_id', '!=', False)]}"/>
                                <field name="street2" placeholder="Street 2..." class="o_address_street" attrs="{'readonly': [('type', '=', 'contact'),('parent_id', '!=', False)]}"/>
                                <field name="city" placeholder="City" class="o_address_city" attrs="{'readonly': [('type', '=', 'contact'),('parent_id', '!=', False)]}"/>
                                <field name="state_id" class="o_address_state" placeholder="State" options="{&quot;no_open&quot;: True}" on_change="onchange_state(state_id)" attrs="{'readonly': [('type', '=', 'contact'),('parent_id', '!=', False)]}" context="{'country_id': country_id, 'zip': zip}"/>
                                <field name="zip" placeholder="ZIP" class="o_address_zip" attrs="{'readonly': [('type', '=', 'contact'),('parent_id', '!=', False)]}"/>
                                <field name="country_id" placeholder="Country" class="o_address_country" options="{&quot;no_open&quot;: True, &quot;no_create&quot;: True}" attrs="{'readonly': [('type', '=', 'contact'),('parent_id', '!=', False)]}"/>
                            </div>
                            <field name="website" widget="url" placeholder="e.g. www.odoo.com"/>
                        </group>
                        <group>
                            <field name="function" placeholder="e.g. Sales Director" attrs="{'invisible': [('is_company','=', True)]}"/>
                            <field name="phone" widget="phone"/>
                            <field name="mobile" widget="phone"/>
                            <field name="user_ids" invisible="1"/>
                            <field name="email" widget="email" attrs="{'required': [('user_ids','!=', [])]}"/>
                            <field name="title" options="{&quot;no_open&quot;: True}" attrs="{'invisible': [('is_company', '=', True)]}"/>
                            <field name="lang"/>
                            <field name="category_id" widget="many2many_tags" placeholder="Tags..."/>
                        </group>
                    </group>

                    <notebook colspan="4">
                        <page string="Contacts &amp; Addresses" autofocus="autofocus">
                            <field name="child_ids" mode="kanban" context="{'default_parent_id': active_id, 'default_street': street, 'default_street2': street2, 'default_city': city, 'default_state_id': state_id, 'default_zip': zip, 'default_country_id': country_id, 'default_supplier': supplier, 'default_customer': customer, 'default_lang': lang,}">
                                <kanban>
                                    <field name="color"/>
                                    <field name="name"/>
                                    <field name="title"/>
                                    <field name="type"/>
                                    <field name="email"/>
                                    <field name="parent_id"/>
                                    <field name="is_company"/>
                                    <field name="function"/>
                                    <field name="phone"/>
                                    <field name="street"/>
                                    <field name="street2"/>
                                    <field name="zip"/>
                                    <field name="city"/>
                                    <field name="country_id"/>
                                    <field name="mobile"/>
                                    <field name="state_id"/>
                                    <field name="image"/>
                                    <field name="lang"/>
                                </kanban>
                            </field>
                        </page>
                    </notebook>
                </sheet>
            </form>
            """,
            'model': 'res.partner'})
        self.studio_controller = WebStudioController()

    def _test_view_normalization(self, original, expected):
        original = original and textwrap.dedent(original)
        self.studio_controller._set_studio_view(self.view, original)

        studio_view = self.studio_controller._get_studio_view(self.view)
        studio_view = studio_view.with_context(load_all_views=True)
        normalized = studio_view.normalize()

        self.studio_controller._set_studio_view(self.view, normalized)
        self.env[self.view.model].with_context(studio=True, load_all_views=True).fields_view_get(self.view.id, self.view.type)

        normalized = normalized and normalized.strip()
        expected = expected and textwrap.dedent(expected).strip()
        self.assertEqual(normalized, expected)

    # Flatten all xpath that target nodes added by studio itself
    def test_view_normalization_00(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="/form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG">
                  <group name="studio_group_E16QG_left" string="Left Title"/>
                  <group name="studio_group_E16QG_right" string="Right Title"/>
                </group>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_left']" position="inside">
                <field name="credit_limit"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_left']" position="after">
                <field name="id"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_right']" position="inside">
                <field name="employee"/>
              </xpath>
              <xpath expr="//field[@name='credit_limit']" position="after">
                <field name="contact_address"/>
              </xpath>
            </data>
        """, """
            <data>
              <xpath expr="//form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG">
                  <group name="studio_group_E16QG_left" string="Left Title">
                    <field name="credit_limit"/>
                    <field name="contact_address"/>
                  </group>
                  <field name="id"/>
                  <group name="studio_group_E16QG_right" string="Right Title">
                    <field name="employee"/>
                  </group>
                </group>
              </xpath>
            </data>
        """)

    # Delete children of deleted nodes and reanchor siblings
    def test_view_normalization_01(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="/form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG">
                  <group name="studio_group_E16QG_left" string="Left Title"/>
                  <group name="studio_group_E16QG_right" string="Right Title"/>
                </group>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_left']" position="inside">
                <field name="credit_limit"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_left']" position="after">
                <field name="id"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_right']" position="inside">
                <field name="employee"/>
              </xpath>
              <xpath expr="//field[@name='credit_limit']" position="after">
                <field name="contact_address"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_left']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG">
                  <field name="id"/>
                  <group name="studio_group_E16QG_right" string="Right Title">
                    <field name="employee"/>
                  </group>
                </group>
              </xpath>
            </data>
        """)

    # When there is no more sibling, we need to reanchor on the parent
    def test_view_normalization_02(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="/form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG">
                  <group name="studio_group_E16QG_right" string="Right Title"/>
                </group>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_right']" position="before">
                <field name="id"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_right']" position="inside">
                <field name="employee"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_right']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG">
                  <field name="id"/>
                </group>
              </xpath>
            </data>
        """)

    # When a field is deleted, other xpath that targets it need to be reanchored.
    def test_view_normalization_03(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="/form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG">
                  <group name="studio_group_E16QG_right" string="Right Title"/>
                </group>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_right']" position="before">
                <field name="id"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_right']" position="inside">
                <field name="employee"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG_right']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG">
                  <field name="id"/>
                </group>
              </xpath>
            </data>
        """)

    # If there is nothing left in the studio view, delete it.
    def test_view_normalization_04(self):
        expected = ''
        self._test_view_normalization("""
            <data>
              <xpath expr="/form[1]/sheet[1]/group[1]" position="after">
                <group name="studio_group_E16QG"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG']" position="inside">
                <field name="id"/>
              </xpath>
              <xpath expr="//field[@name='id']" position="after">
                <field name="create_uid"/>
              </xpath>
              <xpath expr="//group[@name='studio_group_E16QG']" position="replace"/>
            </data>
        """, expected)
        studio_view = self.studio_controller._set_studio_view(self.view, expected)
        studio_view = self.studio_controller._get_studio_view(self.view)
        self.assertEqual(len(studio_view), 0)

    # An after can become a replace if the following sibling has been removed.
    def test_view_normalization_05(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//field[@name='mobile']" position="after">
                <field name="contact_address"/>
              </xpath>
              <xpath expr="//field[@name='mobile']" position="replace"/>
              <xpath expr="//field[@name='contact_address']" position="after">
                <field name="tz"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//field[@name='mobile']" position="replace">
                <field name="tz"/>
              </xpath>
            </data>
        """)

    # Multiple additions of fields should not appear if it was deleted
    def test_view_normalization_06(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//field[@name='website']" position="after">
                <field name="color"/>
              </xpath>
              <xpath expr="//field[@name='color']" position="replace">
              </xpath>
              <xpath expr="//field[@name='category_id']" position="after">
                <field name="color"/>
              </xpath>
              <xpath expr="//field[@name='color']" position="after">
                <field name="create_date"/>
              </xpath>
              <xpath expr="//field[@name='color']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//field[@name='category_id']" position="after">
                <field name="create_date"/>
              </xpath>
            </data>
        """)

    # Consecutive xpaths around a field that was moved away can be merged.
    def test_view_normalization_07(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//field[@name='mobile']" position="after">
                <field name="contact_address"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="after">
                  <field name="tz"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="replace"/>
              <xpath expr="//field[@name='tz']" position="after">
                  <field name="contact_address"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="after">
                  <field name="create_uid"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//field[@name='mobile']" position="after">
                <field name="tz"/>
                <field name="create_uid"/>
              </xpath>
            </data>
        """)

    # A field that was added, then moved then deleted should not appear.
    def test_view_normalization_08(self):
        self._test_view_normalization("""
          <data>
            <xpath expr="//field[@name='website']" position="after">
              <field name="color"/>
            </xpath>
            <xpath expr="//field[@name='color']" position="replace">
              <field name="create_uid"/>
            </xpath>
            <xpath expr="//field[@name='category_id']" position="after">
              <field name="color"/>
            </xpath>
            <xpath expr="//field[@name='color']" position="after">
              <field name="create_date"/>
            </xpath>
            <xpath expr="//field[@name='color']" position="replace"/>
          </data>
        """, """
          <data>
            <xpath expr="//field[@name='website']" position="after">
              <field name="create_uid"/>
            </xpath>
            <xpath expr="//field[@name='category_id']" position="after">
              <field name="create_date"/>
            </xpath>
          </data>
        """)

    # Fields that were added then removed should not appear in the view at all,
    # and every other xpath that was using it should be reanchored elsewhere.
    def test_view_normalization_09(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//field[@name='phone']" position="after">
                <field name="contact_address"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="replace">
                  <field name="id"/>
              </xpath>
              <xpath expr="//field[@name='mobile']" position="after">
                  <field name="contact_address"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="after">
                  <field name="create_uid"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//field[@name='phone']" position="after">
                <field name="id"/>
              </xpath>
              <xpath expr="//field[@name='mobile']" position="after">
                <field name="create_uid"/>
              </xpath>
            </data>
        """)

    # When two fields are added after a given field, the second one will appear
    # before the first one.
    def test_view_normalization_10(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//field[@name='phone']" position="replace">
                <field name="create_date"/>
              </xpath>
              <xpath expr="//field[@name='create_date']" position="after">
                  <field name="id"/>
              </xpath>
              <xpath expr="//field[@name='create_date']" position="after">
                <field name="contact_address"/>
              </xpath>
              <xpath expr="//field[@name='create_date']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//field[@name='phone']" position="replace">
                <field name="contact_address"/>
                <field name="id"/>
              </xpath>
            </data>
        """)

    # When we add a field after another one and replace the sibling of this one,
    # everything could be done in a single replace on the sibling node.
    def test_view_normalization_11(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//field[@name='phone']" position="after">
                <field name="create_uid"/>
              </xpath>
              <xpath expr="//field[@name='phone']" position="replace">
                <field name="create_date"/>
              </xpath>
              <xpath expr="//field[@name='create_date']" position="after">
                  <field name="id"/>
              </xpath>
              <xpath expr="//field[@name='create_date']" position="replace"/>
              <xpath expr="//field[@name='create_uid']" position="before">
                <field name="create_date"/>
              </xpath>
              <xpath expr="//field[@name='create_date']" position="after">
                  <field name="mobile"/>
              </xpath>
              <xpath expr="//field[@name='create_date']" position="replace"/>
            </data>
        """, """
            <data>
              <xpath expr="//field[@name='phone']" position="replace">
                <field name="id"/>
                <field name="mobile"/>
                <field name="create_uid"/>
              </xpath>
            </data>
        """)

    # When closest previous node has no name, the closest next node should be
    # used instead, provided it has a name. Also, attributes need to be handled
    # in a single xpath and alphabetically sorted.
    def test_view_normalization_12(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="attributes">
                <attribute name="zzz">PAGE 1 ZZZ</attribute>
              </xpath>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="after">
                <page name="PAGE_2" string="AWESOME PAGE 2"/>
              </xpath>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="attributes">
                <attribute name="help">PAGE 1 HELP</attribute>
              </xpath>
            </data>
        """, """
            <data>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="attributes">
                <attribute name="help">PAGE 1 HELP</attribute>
                <attribute name="zzz">PAGE 1 ZZZ</attribute>
              </xpath>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="after">
                <page name="PAGE_2" string="AWESOME PAGE 2"/>
              </xpath>
            </data>
        """)

    # Changing an already existing attribute will generate a remove line for
    # the previous value and an addition line for the new value. The removing
    # line should not close the attributes xpath, both attributes need to be
    # redefined in a single xpath.
    def test_view_normalization_13(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="attributes">
                <attribute name="string">PAGE 1</attribute>
              </xpath>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="after">
                <page name="PAGE_2" string="AWESOME PAGE 2"/>
              </xpath>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="attributes">
                <attribute name="help">PAGE 1 HELP</attribute>
              </xpath>
            </data>
        """, """
            <data>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="attributes">
                <attribute name="help">PAGE 1 HELP</attribute>
                <attribute name="string">PAGE 1</attribute>
              </xpath>
              <xpath expr="//form[1]/sheet[1]/notebook[1]/page[1]" position="after">
                <page name="PAGE_2" string="AWESOME PAGE 2"/>
              </xpath>
            </data>
        """)

    def test_view_normalization_14(self):
        # There is already a chatter on res.partner.form view, which is why
        # the resulting xpath is /div instead of /sheet.
        self._test_view_normalization("""
            <data>
              <xpath expr="/form[1]/*[last()]" position="after">
                <div class="oe_chatter">
                  <field name="message_follower_ids" widget="mail_followers"/>
                  <field name="message_ids" widget="mail_thread"/>
                </div>
              </xpath>
            </data>
        """, """
            <data>
              <xpath expr="//form[1]/sheet[1]" position="after">
                <div class="oe_chatter">
                  <field name="message_follower_ids" widget="mail_followers"/>
                  <field name="message_ids" widget="mail_thread"/>
                </div>
              </xpath>
            </data>
        """)

    # Don't break on text with newlines
    def test_view_normalization_15(self):
        # New lines in text used to create a new line in the diff, desynchronizing
        # the diff lines and the tree elements iterator
        self._test_view_normalization("""
            <data>
              <xpath expr="//field[@name='phone']" position="replace">
                <h1>
                    THIS
                    IS
                    A MULTILINE
                    TITLE
                </h1>
              </xpath>
            </data>
        """, """
            <data>
              <xpath expr="//field[@name='phone']" position="replace">
                <h1>
                    THIS
                    IS
                    A MULTILINE
                    TITLE
                </h1>
              </xpath>
            </data>
        """)

    # Test anchoring next to studio fields
    def test_view_normalization_16(self):
        self._test_view_normalization("""
            <data>
              <xpath expr="//field[@name='mobile']" position="after">
                <field name="contact_address"/>
              </xpath>
              <xpath expr="//field[@name='contact_address']" position="after">
                <field name="tz"/>
              </xpath>
              <xpath expr="//field[@name='tz']" position="before">
                <field name="phone"/>
              </xpath>
            </data>
        """, """
            <data>
              <xpath expr="//field[@name='mobile']" position="after">
                <field name="contact_address"/>
                <field name="phone"/>
                <field name="tz"/>
              </xpath>
            </data>
        """)

    def tearDown(self):
        super(TestViewNormalization, self).tearDown()
        _request_stack.pop()
