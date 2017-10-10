from odoo.tests import common


class TestWebsiteVersionBase(common.TransactionCase):

    def setUp(self):
        super(TestWebsiteVersionBase, self).setUp()

        # Usefull models
        self.ir_ui_view = self.env['ir.ui.view']
        self.website_version_version = self.env['website_version.version']
        self.website = self.env['website']
        self.ir_model_data = self.env['ir.model.data']

        #Usefull objects
        master_view = self.env.ref('website.website2_homepage')
        self.arch_master = master_view.arch
        self.version = self.env.ref('website_version.version_0_0_0_0')
        self.website = self.env.ref('website.website2')
        self.view_0_0_0_0 = self.env.ref('website_version.website2_homepage_other')
        self.arch_0_0_0_0 = self.view_0_0_0_0.arch
