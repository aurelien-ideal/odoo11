odoo.define('website_sign.views_custo', function(require) {
    'use strict';

    var core = require('web.core');
    var KanbanController = require("web.KanbanController");
    var KanbanColumn = require("web.KanbanColumn");
    var KanbanRecord = require("web.KanbanRecord");
    var ListController = require("web.ListController");

    var _t = core._t;

    KanbanController.include(_make_custo("button.o-kanban-button-new"));
    ListController.include(_make_custo(".o_list_button_add"));

    KanbanColumn.include({
        /**
         * @override
         */
        start: function () {
            var def = this._super.apply(this, arguments);
            if (this.modelName !== "signature.request") {
                return def;
            }

            var self = this;
            return def.done(function () {
                self.$el.sortable("destroy");
            });
        },
    });

    KanbanRecord.include({
        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * @override
         * @private
         */
        _openRecord: function () {
            if (this.modelName === "signature.request" || this.modelName === "signature.request.template") {
                var $link = this.$(".o_sign_action_link");
                if ($link.length) {
                    this.trigger_up('button_clicked', {
                        attrs: $link.data(),
                        record: this.state,
                    });
                    return;
                }
            }
            return this._super.apply(this, arguments);
        },
    });

    function _make_custo(selector_button) {
        return {
            renderButtons: function () {
                this._super.apply(this, arguments);

                if (this.modelName === "signature.request.template") {
                    this._website_sign_upload_file_button();
                } else if (this.modelName === "signature.request") {
                    this._website_sign_create_request_button();
                }
            },

            _website_sign_upload_file_button: function () {
                var self = this;
                this.$buttons.find(selector_button).text(_t("Upload a PDF Template")).off("click").on("click", function (e) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    _website_sign_upload_file.call(self);
                });
            },

            _website_sign_create_request_button: function () {
                var self = this;
                this.$buttons.find(selector_button).text(_t("Request a Signature")).off("click").on("click", function (e) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    _website_sign_create_request.call(self);
                });
            },
        };
    }

    function _website_sign_upload_file() {
        var self = this;
        var $upload_input = $('<input type="file" name="files[]"/>');
        $upload_input.on('change', function (e) {
            var f = e.target.files[0];
            var reader = new FileReader();

            reader.onload = function(e) {
                self._rpc({
                        model: 'signature.request.template',
                        method: 'upload_template',
                        args: [f.name, e.target.result],
                    })
                    .then(function(data) {
                        self.do_action({
                                type: "ir.actions.client",
                                tag: 'website_sign.Template',
                                name: _t("New Template"),
                                context: {
                                    id: data.template,
                                },
                            });
                        })
                    .always(function() {
                        $upload_input.removeAttr('disabled');
                        $upload_input.val("");
                    });
            };
            try {
                reader.readAsDataURL(f);
            } catch (e) {
                console.warn(e);
            }
        });

        $upload_input.click();
    }

    function _website_sign_create_request() {
        this.do_action("website_sign.signature_request_template_action");
    }
});

odoo.define('website_sign.template', function(require) {
    'use strict';

    var ControlPanelMixin = require('web.ControlPanelMixin');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var framework = require('web.framework');
    var session = require('web.session');
    var Widget = require('web.Widget');
    var PDFIframe = require('website_sign.PDFIframe');
    var website_sign_utils = require('website_sign.utils');

    var _t = core._t;

    var SignatureItemCustomDialog = Dialog.extend({
        template: 'website_sign.signature_item_custom_dialog',

        init: function(parent, parties, options) {
            options = options || {};

            options.title = options.title || _t("Customize Field");
            options.size = options.size || "medium";

            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: 'Save', classes: 'btn-primary', close: true, click: function(e) {
                    var resp = parseInt(this.$responsibleSelect.find('select').val());
                    var required = this.$('input[type="checkbox"]').prop('checked');
                    var name = this.$('#o_sign_name').val();

                    this.getParent().currentRole = resp;
                    this.$currentTarget.data({responsible: resp, required: required, name: name}).trigger('itemChange');
                }});
                options.buttons.push({text: _t('Remove'), classes: 'o_sign_delete_field_button btn-link', close: true, click: function(e) {
                    this.$currentTarget.trigger('itemDelete');
                }});
                options.buttons.push({text: 'Discard', classes: 'btn-default', close: true});
            }

            this._super(parent, options);

            this.parties = parties;
        },

        start: function() {
            this.$responsibleSelect = this.$('.o_sign_responsible_select');

            var self = this;
            return this._super().then(function() {
                website_sign_utils.setAsResponsibleSelect(self.$responsibleSelect.find('select'), self.$currentTarget.data('responsible'), self.parties);
                self.$('input[type="checkbox"]').prop('checked', self.$currentTarget.data('required'));

                self.$('#o_sign_name').val(self.$currentTarget.data('name') );
                self.set_title(self.title, '<span class="fa fa-long-arrow-right"/> ' + self.$currentTarget.prop('title') + ' Field');
            });
        },

        open: function($signatureItem) {
            this.$currentTarget = $signatureItem;
            this._super.apply(this, arguments);
        },
    });

    var InitialAllPagesDialog = Dialog.extend({
        template: 'website_sign.initial_all_pages_dialog',

        init: function(parent, parties, options) {
            options = options || {};

            options.title = options.title || _t("Add Initials");
            options.size = options.size || "medium";

            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: _t('Add once'), classes: 'btn-primary', close: true, click: function(e) {
                    this.updateTargetResponsible();
                    this.$currentTarget.trigger('itemChange');
                }});
                options.buttons.push({text: _t('Add on all pages'), classes: 'btn-default', close: true, click: function(e) {
                    this.updateTargetResponsible();
                    this.$currentTarget.draggable('destroy').resizable('destroy');
                    this.$currentTarget.trigger('itemClone');
                }});
            }

            this._super(parent, options);

            this.parties = parties;
        },

        start: function() {
            this.$responsibleSelect = this.$('.o_sign_responsible_select_initials');

            var self = this;
            return this._super.apply(this, arguments).then(function() {
                website_sign_utils.setAsResponsibleSelect(self.$responsibleSelect.find('select'), self.getParent().currentRole, self.parties);
            });
        },

        open: function($signatureItem) {
            this.$currentTarget = $signatureItem;
            this._super.apply(this, arguments);
        },

        updateTargetResponsible: function() {
            var resp = parseInt(this.$responsibleSelect.find('select').val());
            this.getParent().currentRole = resp;
            this.$currentTarget.data('responsible', resp);
        },
    });

    var CreateSignatureRequestDialog = Dialog.extend({
        template: 'website_sign.create_signature_request_dialog',

        init: function(parent, templateID, rolesToChoose, templateName, attachment, options) {
            options = options || {};

            options.title = options.title || _t("Send Signature Request");
            options.size = options.size || "medium";

            options.buttons = (options.buttons || []);
            options.buttons.push({text: _t('Send'), classes: 'btn-primary', click: function(e) {
                this.sendDocument();
            }});
            options.buttons.push({text: _t('Cancel'), classes: 'btn-default', close: true});

            this._super(parent, options);

            this.templateID = templateID;
            this.rolesToChoose = rolesToChoose;
            this.templateName = templateName;
            this.attachment = attachment;
        },

        willStart: function() {
            var self = this;
            return $.when(this._super(),
                this._rpc({
                        model: 'res.users',
                        method: 'read',
                        args: [[session.uid], ['partner_id']],
                    })
                    .then(function(user) {
                        return self._rpc({
                                model: 'res.partner',
                                method: 'read',
                                args: [[user[0].partner_id[0]], ['name']],
                            })
                            .then(prepare_reference);
                        })
            );

            function prepare_reference(partner) {
                self.default_reference = "-";
                var split = partner[0].name.split(' ');
                for(var i = 0 ; i < split.length ; i++) {
                    self.default_reference += split[i][0];
                }
            }
        },

        start: function() {
            this.$subjectInput = this.$('.o_sign_subject_input').first();
            this.$messageInput = this.$('.o_sign_message_textarea').first();
            this.$referenceInput = this.$('.o_sign_reference_input').first();

            this.$subjectInput.val('Signature Request - ' + this.templateName);
            var defaultRef = this.templateName + this.default_reference;
            this.$referenceInput.val(defaultRef).attr('placeholder', defaultRef);

            this.$('.o_sign_warning_message_no_field').first().toggle($.isEmptyObject(this.rolesToChoose));
            this.$('.o_sign_request_signers .o_sign_new_signer').remove();

            website_sign_utils.setAsPartnerSelect(this.$('.o_sign_request_signers .form-group input[type="hidden"]')); // Followers

            if($.isEmptyObject(this.rolesToChoose)) {
                this.addSigner(0, _t("Signers"), true);
            } else {
                var roleIDs = Object.keys(this.rolesToChoose).sort();
                for(var i = 0 ; i < roleIDs.length ; i++) {
                    var roleID = roleIDs[i];
                    if(roleID !== 0)
                        this.addSigner(roleID, this.rolesToChoose[roleID], false);
                }
            }

            return this._super.apply(this, arguments);
        },

        addSigner: function(roleID, roleName, multiple) {
            var $newSigner = $('<div/>').addClass('o_sign_new_signer form-group');

            $newSigner.append($('<label/>').addClass('col-md-3').text(roleName).data('role', roleID));

            var $signerInfo = $('<input type="hidden"/>').attr('placeholder', _t("Write email or search contact..."));
            if(multiple) {
                $signerInfo.attr('multiple', 'multiple');
            }

            var $signerInfoDiv = $('<div/>').addClass('col-md-9');
            $signerInfoDiv.append($signerInfo);

            $newSigner.append($signerInfoDiv);

            website_sign_utils.setAsPartnerSelect($signerInfo);

            this.$('.o_sign_request_signers').first().prepend($newSigner);
        },

        sendDocument: function() {
            var self = this;

            var completedOk = true;
            self.$('.o_sign_new_signer').each(function(i, el) {
                var $elem = $(el);
                var partnerIDs = $elem.find('input[type="hidden"]').val();
                if(!partnerIDs || partnerIDs.length <= 0) {
                    completedOk = false;
                    $elem.addClass('has-error');
                    $elem.one('focusin', function(e) {
                        $elem.removeClass('has-error');
                    });
                }
            });
            if(!completedOk) {
                return false;
            }

            var waitFor = [];

            var signers = [];
            self.$('.o_sign_new_signer').each(function(i, el) {
                var $elem = $(el);
                var selectDef = website_sign_utils.processPartnersSelection($elem.find('input[type="hidden"]')).then(function(partners) {
                    for(var p = 0 ; p < partners.length ; p++) {
                        signers.push({
                            'partner_id': partners[p],
                            'role': parseInt($elem.find('label').data('role'))
                        });
                    }
                });
                if(selectDef !== false) {
                    waitFor.push(selectDef);
                }
            });

            var followers = [];
            var followerDef = website_sign_utils.processPartnersSelection(self.$('#o_sign_followers_select')).then(function(partners) {
                followers = partners;
            });
            if(followerDef !== false) {
                waitFor.push(followerDef);
            }

            var subject = self.$subjectInput.val() || self.$subjectInput.attr('placeholder');
            var reference = self.$referenceInput.val() || self.$referenceInput.attr('placeholder');
            var message = self.$messageInput.val();
            $.when.apply($, waitFor).then(function(result) {
                self._rpc({
                        model: 'signature.request',
                        method: 'initialize_new',
                        args: [self.templateID, signers, followers, reference, subject, message],
                    })
                    .then(function(sr) {
                        self.do_notify(_t("Success"), _("Your signature request has been sent."));
                        self.do_action({
                            type: "ir.actions.client",
                            tag: 'website_sign.Document',
                            name: _t("New Document"),
                            context: {
                                id: sr.id,
                                token: sr.token,
                                sign_token: sr.sign_token || null,
                                create_uid: session.uid,
                                state: 'sent',
                            },
                        });
                    }).always(function() {
                        self.close();
                    });
            });
        },
    });

    var ShareTemplateDialog = Dialog.extend({
        template: 'website_sign.share_template_dialog',

        events: {
            'focus input': function(e) {
                $(e.target).select();
            },
        },

        init: function(parent, templateID, options) {
            options = options || {};
            options.title = options.title || _t("Multiple Signature Requests");
            options.size = options.size || "medium";

            this.templateID = templateID;
            this._super(parent, options);
        },

        start: function() {
            var $linkInput = this.$('input').first();
            var linkStart = window.location.href.substr(0, window.location.href.indexOf('/web')) + '/sign/';

            return $.when(
                this._super(),
                this._rpc({
                        model: 'signature.request.template',
                        method: 'share',
                        args: [this.templateID],
                    })
                    .then(function(link) {
                        $linkInput.val((link)? (linkStart + link) : '');
                        $linkInput.parent().toggle(!!link).next().toggle(!link);
                    })
            );
        },
    });

    var EditablePDFIframe = PDFIframe.extend({
        init: function() {
            this._super.apply(this, arguments);

            this.events = _.extend(this.events || {}, {
                'itemChange .o_sign_signature_item': function(e) {
                    this.updateSignatureItem($(e.target));
                    this.$iframe.trigger('templateChange');
                },

                'itemDelete .o_sign_signature_item': function(e) {
                    this.deleteSignatureItem($(e.target));
                    this.$iframe.trigger('templateChange');
                },

                'itemClone .o_sign_signature_item': function(e) {
                    var $target = $(e.target);
                    this.updateSignatureItem($target);

                    page_loop:
                    for(var i = 1 ; i <= this.nbPages ; i++) {
                        for(var j = 0 ; j < this.configuration[i].length ; j++) {
                            if(this.types[this.configuration[i][j].data('type')].type === 'signature') {
                                continue page_loop;
                            }
                        }

                        var $newElem = $target.clone(true);
                        this.enableCustom($newElem);
                        this.configuration[i].push($newElem);
                    }

                    this.deleteSignatureItem($target);
                    this.refreshSignatureItems();
                    this.$iframe.trigger('templateChange');
                },
            });
        },

        doPDFPostLoad: function() {
            var self = this;
            this.fullyLoaded.then(function() {
                if(self.editMode) {
                    if(self.$iframe.prop('disabled')) {
                        self.$('#viewer').fadeTo('slow', 0.75);
                        var $div = $('<div/>').css({
                            position: "absolute",
                            top: 0,
                            left: 0,
                            width: "100%",
                            height: "100%",
                            'z-index': 110,
                            opacity: 0.75
                        });
                        self.$('#viewer').css('position', 'relative').prepend($div);
                        $div.on('click mousedown mouseup mouveover mouseout', function(e) {
                            return false;
                        });
                    } else {
                        self.$hBarTop = $('<div/>');
                        self.$hBarBottom = $('<div/>');
                        self.$hBarTop.add(self.$hBarBottom).css({
                            position: 'absolute',
                            "border-top": "1px dashed orange",
                            width: "100%",
                            height: 0,
                            "z-index": 103,
                            left: 0
                        });
                        self.$vBarLeft = $('<div/>');
                        self.$vBarRight = $('<div/>');
                        self.$vBarLeft.add(self.$vBarRight).css({
                            position: 'absolute',
                            "border-left": "1px dashed orange",
                            width: 0,
                            height: "10000px",
                            "z-index": 103,
                            top: 0
                        });

                        var typesArr = _.toArray(self.types);
                        var $fieldTypeButtons = $(core.qweb.render('website_sign.type_buttons', {signature_item_types: typesArr}));
                        self.$fieldTypeToolbar = $('<div/>').addClass('o_sign_field_type_toolbar');
                        self.$fieldTypeToolbar.prependTo(self.$('#viewerContainer'));
                        $fieldTypeButtons.appendTo(self.$fieldTypeToolbar).draggable({
                            cancel: false,
                            helper: function(e) {
                                var type = self.types[$(this).data('item-type-id')];
                                var $signatureItem = self.createSignatureItem(type, true, self.currentRole, 0, 0, type.default_width, type.default_height, '');

                                if(!e.ctrlKey) {
                                    self.$('.o_sign_signature_item').removeClass('ui-selected');
                                }
                                $signatureItem.addClass('o_sign_signature_item_to_add ui-selected');

                                self.$('.page').first().append($signatureItem);
                                self.updateSignatureItem($signatureItem);
                                $signatureItem.css('width', $signatureItem.css('width')).css('height', $signatureItem.css('height')); // Convert % to px
                                $signatureItem.detach();

                                return $signatureItem;
                            }
                        });
                        $fieldTypeButtons.each(function(i, el) {
                            self.enableCustomBar($(el));
                        });

                        self.$('.page').droppable({
                            accept: '*',
                            tolerance: 'touch',
                            drop: function(e, ui) {
                                if(!ui.helper.hasClass('o_sign_signature_item_to_add')) {
                                    return true;
                                }

                                var $parent = $(e.target);
                                var pageNo = parseInt($parent.prop('id').substr('pageContainer'.length));

                                ui.helper.removeClass('o_sign_signature_item_to_add');
                                var $signatureItem = ui.helper.clone(true).removeClass().addClass('o_sign_signature_item o_sign_signature_item_required');

                                var posX = (ui.offset.left - $parent.find('.textLayer').offset().left) / $parent.innerWidth();
                                var posY = (ui.offset.top - $parent.find('.textLayer').offset().top) / $parent.innerHeight();
                                $signatureItem.data({posx: posX, posy: posY});

                                self.configuration[pageNo].push($signatureItem);
                                self.refreshSignatureItems();
                                self.updateSignatureItem($signatureItem);
                                self.enableCustom($signatureItem);

                                self.$iframe.trigger('templateChange');

                                if(self.types[$signatureItem.data('type')].type === 'initial') {
                                    (new InitialAllPagesDialog(self, self.parties)).open($signatureItem);
                                }

                                return false;
                            }
                        });

                        self.$('#viewer').selectable({
                            appendTo: self.$('body'),
                            filter: '.o_sign_signature_item',
                        });

                        $(document).add(self.$el).on('keyup', function(e) {
                            if(e.which !== 46) {
                                return true;
                            }

                            self.$('.ui-selected').each(function(i, el) {
                                self.deleteSignatureItem($(el));
                            });
                            self.$iframe.trigger('templateChange');
                        });
                    }

                    self.$('.o_sign_signature_item').each(function(i, el) {
                        self.enableCustom($(el));
                    });
                }
            });

            this._super.apply(this, arguments);
        },

        enableCustom: function($signatureItem) {
            var self = this;

            $signatureItem.prop('title', this.types[$signatureItem.data('type')].name);

            var $configArea = $signatureItem.find('.o_sign_config_area');

            $configArea.find('.o_sign_responsible_display').off('mousedown').on('mousedown', function(e) {
                e.stopPropagation();
                self.$('.ui-selected').removeClass('ui-selected');
                $signatureItem.addClass('ui-selected');

                (new SignatureItemCustomDialog(self, self.parties)).open($signatureItem);
            });

            $configArea.find('.fa.fa-arrows').off('mouseup').on('mouseup', function(e) {
                if(!e.ctrlKey) {
                    self.$('.o_sign_signature_item').filter(function(i) {
                        return (this !== $signatureItem[0]);
                    }).removeClass('ui-selected');
                }
                $signatureItem.toggleClass('ui-selected');
            });

            $signatureItem.draggable({containment: "parent", handle: ".fa-arrows"}).resizable({containment: "parent"}).css('position', 'absolute');

            $signatureItem.off('dragstart resizestart').on('dragstart resizestart', function(e, ui) {
                if(!e.ctrlKey) {
                    self.$('.o_sign_signature_item').removeClass('ui-selected');
                }
                $signatureItem.addClass('ui-selected');
            });

            $signatureItem.off('dragstop').on('dragstop', function(e, ui) {
                $signatureItem.data({
                    posx: Math.round((ui.position.left / $signatureItem.parent().innerWidth())*1000)/1000,
                    posy: Math.round((ui.position.top / $signatureItem.parent().innerHeight())*1000)/1000,
                });
            });

            $signatureItem.off('resizestop').on('resizestop', function(e, ui) {
                $signatureItem.data({
                    width: Math.round(ui.size.width/$signatureItem.parent().innerWidth()*1000)/1000,
                    height: Math.round(ui.size.height/$signatureItem.parent().innerHeight()*1000)/1000,
                });
            });

            $signatureItem.on('dragstop resizestop', function(e, ui) {
                self.updateSignatureItem($signatureItem);
                self.$iframe.trigger('templateChange');
                $signatureItem.removeClass('ui-selected');
            });

            this.enableCustomBar($signatureItem);
        },

        enableCustomBar: function($item) {
            var self = this;

            $item.on('dragstart resizestart', function(e, ui) {
                start.call(self, ui.helper);
            });
            $item.find('.o_sign_config_area .fa.fa-arrows').on('mousedown', function(e) {
                start.call(self, $item);
                process.call(self, $item, $item.position());
            });
            $item.on('drag resize', function(e, ui) {
                process.call(self, ui.helper, ui.position);
            });
            $item.on('dragstop resizestop', function(e, ui) {
                end.call(self);
            });
            $item.find('.o_sign_config_area .fa.fa-arrows').on('mouseup', function(e) {
                end.call(self);
            });

            function start($helper) {
                this.$hBarTop.detach().insertAfter($helper).show();
                this.$hBarBottom.detach().insertAfter($helper).show();
                this.$vBarLeft.detach().insertAfter($helper).show();
                this.$vBarRight.detach().insertAfter($helper).show();
            }
            function process($helper, position) {
                this.$hBarTop.css('top', position.top);
                this.$hBarBottom.css('top', position.top+parseFloat($helper.css('height'))-1);
                this.$vBarLeft.css('left', position.left);
                this.$vBarRight.css('left', position.left+parseFloat($helper.css('width'))-1);
            }
            function end() {
                this.$hBarTop.hide();
                this.$hBarBottom.hide();
                this.$vBarLeft.hide();
                this.$vBarRight.hide();
            }
        },

        updateSignatureItem: function($signatureItem) {
            this._super.apply(this, arguments);

            if(this.editMode) {
                var responsibleName = this.parties[$signatureItem.data('responsible')].name;
                $signatureItem.find('.o_sign_responsible_display').text(responsibleName).prop('title', responsibleName);
            }
        },
    });

    var Template = Widget.extend(ControlPanelMixin, {
        className: "o_sign_template",

        events: {
            'click .fa-pencil': function(e) {
                this.$templateNameInput.focus().select();
            },

            'input .o_sign_template_name_input': function(e) {
                this.$templateNameInput.attr('size', this.$templateNameInput.val().length);
            },

            'change .o_sign_template_name_input': function(e) {
                this.saveTemplate();
                if(this.$templateNameInput.val() === "") {
                    this.$templateNameInput.val(this.initialTemplateName);
                }
            },

            'keydown .o_sign_template_name_input': function (e) {
                if (e.keyCode === 13) {
                    this.$templateNameInput.blur();
                }
            },

            'templateChange iframe.o_sign_pdf_iframe': function(e) {
                this.saveTemplate();
            },

            'click .o_sign_duplicate_signature_template': function(e) {
                this.saveTemplate(true);
            },
        },

        go_back_to_kanban: function() {
            return this.do_action("website_sign.signature_request_template_action", {
                clear_breadcrumbs: true,
            });
        },

        init: function(parent, options) {
            this._super.apply(this, arguments);

            if(options.context.id === undefined) {
                return;
            }

            this.templateID = options.context.id;
            this.rolesToChoose = {};

            var self = this;
            var $sendButton = $('<button/>', {html: _t("Send"), type: "button"})
                .addClass('btn btn-primary btn-sm')
                .on('click', function() {
                    self.prepareTemplateData();
                    (new CreateSignatureRequestDialog(self, self.templateID, self.rolesToChoose, self.$templateNameInput.val(), self.signature_request_template.attachment_id)).open();
                });
            var $shareButton = $('<button/>', {html: _t("Share"), type: "button"})
                .addClass('btn btn-default btn-sm')
                .on('click', function() {
                    (new ShareTemplateDialog(self, self.templateID)).open();
                });
            this.cp_content = {$buttons: $sendButton.add($shareButton)};
        },

        willStart: function() {
            if(this.templateID === undefined) {
                return this._super.apply(this, arguments);
            }
            return $.when(this._super(), this.perform_rpc());
        },

        perform_rpc: function() {
            var self = this;

            var defTemplates = this._rpc({
                    model: 'signature.request.template',
                    method: 'read',
                    args: [[this.templateID]],
                })
                .then(function prepare_template(template) {
                    template = template[0];
                    self.signature_request_template = template;
                    self.has_signature_requests = (template.signature_request_ids.length > 0);

                    var defSignatureItems = self._rpc({
                            model: 'signature.item',
                            method: 'read',
                            args: [[template.id]],
                        })
                        .then(function(signature_items) {
                            self.signature_items = signature_items[0];
                        });
                    var defIrAttachments = self._rpc({
                            model: 'ir.attachment',
                            method: 'read',
                            args: [[template.attachment_id[0]], ['mimetype', 'name', 'datas_fname']],
                        })
                        .then(function(attachment) {
                            attachment = attachment[0];
                            self.signature_request_template.attachment_id = attachment;
                            self.isPDF = (attachment.mimetype.indexOf('pdf') > -1);
                        });

                    return $.when(defSignatureItems, defIrAttachments);
                });

            var defParties = this._rpc({
                    model: 'signature.item.party',
                    method: 'search_read',
                })
                .then(function(parties) {
                    self.signature_item_parties = parties;
                });

            var defItemTypes = this._rpc({
                    model: 'signature.item.type',
                    method: 'search_read',
                })
                .then(function(types) {
                    self.signature_item_types = types;
                });

            return $.when(defTemplates, defParties, defItemTypes);
        },

        start: function() {
            if(this.templateID === undefined) {
                return this.go_back_to_kanban();
            }
            this.initialize_content();
            if(this.$('iframe').length) {
                core.bus.on('DOM_updated', this, init_iframe);
            }
            return this._super();

            function init_iframe() {
                if(this.$el.parents('html').length) {
                    var self = this;
                    framework.blockUI({overlayCSS: {opacity: 0}, blockMsgClass: 'o_hidden'});
                    this.iframeWidget = new EditablePDFIframe(this,
                                                              '/web/image/' + this.signature_request_template.attachment_id.id,
                                                              true,
                                                              {
                                                                  parties: this.signature_item_parties,
                                                                  types: this.signature_item_types,
                                                                  signatureItems: this.signature_items,
                                                              });
                    return this.iframeWidget.attachTo(this.$('iframe')).then(function() {
                        framework.unblockUI();
                        self.iframeWidget.currentRole = self.signature_item_parties[0].id;
                    });
                }
            }
        },

        initialize_content: function() {
            this.$el.append(core.qweb.render('website_sign.template', {widget: this}));

            this.$('iframe,.o_sign_template_name_input').prop('disabled', this.has_signature_requests);

            this.$templateNameInput = this.$('.o_sign_template_name_input').first();
            this.$templateNameInput.trigger('input');
            this.initialTemplateName = this.$templateNameInput.val();

            this.refresh_cp();
        },

        do_show: function() {
            this._super();

            var self = this; // The iFrame cannot be detached, so we 'restart' the widget
            return this.perform_rpc().then(function() {
                if(self.iframeWidget) {
                    self.iframeWidget.destroy();
                    self.iframeWidget = undefined;
                }
                self.$el.empty();
                self.initialize_content();
            });
        },

        refresh_cp: function() {
            this.update_control_panel({
                breadcrumbs: this.getParent().get_breadcrumbs(),
                cp_content: this.cp_content
            });
        },

        prepareTemplateData: function() {
            this.rolesToChoose = {};
            var data = {}, newId = 0;
            var configuration = (this.iframeWidget)? this.iframeWidget.configuration : {};
            for(var page in configuration) {
                for(var i = 0 ; i < configuration[page].length ; i++) {
                    var resp = configuration[page][i].data('responsible');

                    data[configuration[page][i].data('item-id') || (newId--)] = {
                        'type_id': configuration[page][i].data('type'),
                        'required': configuration[page][i].data('required'),
                        'name': configuration[page][i].data('name'),
                        'responsible_id': resp,
                        'page': page,
                        'posX': configuration[page][i].data('posx'),
                        'posY': configuration[page][i].data('posy'),
                        'width': configuration[page][i].data('width'),
                        'height': configuration[page][i].data('height'),
                    };

                    this.rolesToChoose[resp] = this.iframeWidget.parties[resp].name;
                }
            }
            return data;
        },

        saveTemplate: function(duplicate) {
            duplicate = (duplicate === undefined)? false : duplicate;

            var data = this.prepareTemplateData();
            var $majInfo = this.$('.o_sign_template_saved_info').first();

            var self = this;
            this._rpc({
                    model: 'signature.request.template',
                    method: 'update_from_pdfviewer',
                    args: [this.templateID, !!duplicate, data, this.$templateNameInput.val() || this.initialTemplateName],
                })
                .then(function(templateID) {
                    if(!templateID) {
                        Dialog.alert(self, _t('Somebody is already filling a document which uses this template'), {
                            confirm_callback: function() {
                                self.go_back_to_kanban();
                            },
                        });
                    }

                    if(duplicate) {
                        self.do_action({
                            type: "ir.actions.client",
                            tag: 'website_sign.Template',
                            name: _t("Duplicated Template"),
                            context: {
                                id: templateID,
                            },
                        });
                    } else {
                        $majInfo.stop().css('opacity', 1).animate({'opacity': 0}, 1500);
                    }
                });
        },
    });

    core.action_registry.add('website_sign.Template', Template);
});

odoo.define('website_sign.DocumentBackend', function (require) {
    'use strict';

    var ajax = require('web.ajax');
    var ControlPanelMixin = require('web.ControlPanelMixin');
    var core = require('web.core');
    var framework = require('web.framework');
    var Widget = require('web.Widget');
    var Document = require('website_sign.Document');

    var _t = core._t;

    var DocumentBackend = Widget.extend(ControlPanelMixin, {
        className: 'o_sign_document',

        go_back_to_kanban: function () {
            return this.do_action("website_sign.signature_request_action", {
                clear_breadcrumbs: true,
            });
        },

        init: function (parent, options) {
            this._super.apply(this, arguments);

            if(options.context.id === undefined) {
                return;
            }

            this.documentID = options.context.id;
            this.token = options.context.token;
            this.create_uid = options.context.create_uid;
            this.state = options.context.state;

            var self = this;

            this.$downloadButton = $('<a/>', {html: _t("Download Document")}).addClass('btn btn-sm btn-primary o_hidden');
            var $historyButton = $('<button/>', {html: _t("View History"), type: "button"}).addClass('btn btn-sm btn-default');
            $historyButton.on('click', function() {
                if(self.documentPage) {
                    self.documentPage.openChatter();
                }
            });
            this.cp_content = {$buttons: this.$downloadButton.add($historyButton)};
        },

        start: function () {
            var self = this;

            if(this.documentID === undefined) {
                return this.go_back_to_kanban();
            }

            return $.when(this._super(), ajax.jsonRpc('/sign/get_document/' + this.documentID + '/' + this.token, 'call', {'message': this.message}).then(function(html) {
                self.$el.append($(html.trim()));

                var $cols = self.$('.col-md-4').toggleClass('col-md-6 col-md-4');
                var $buttonsContainer = $cols.first().remove();

                var url = $buttonsContainer.find('.o_sign_download_document_button').attr('href');
                self.$downloadButton.attr('href', url).toggleClass('o_hidden', !url);

                var init_page = function() {
                    if(self.$el.parents('html').length) {
                        self.refresh_cp();
                        framework.blockUI({overlayCSS: {opacity: 0}, blockMsgClass: 'o_hidden'});
                        var def;
                        if(!self.documentPage) {
                            self.documentPage = new (self.get_document_class())(self);
                            def = self.documentPage.attachTo(self.$el);
                        } else {
                            def = self.documentPage.initialize_iframe();
                        }
                        def.then(function() {
                            framework.unblockUI();
                        });
                    }
                };
                core.bus.on('DOM_updated', null, init_page);
            }));
        },

        get_document_class: function () {
            return Document;
        },

        refresh_cp: function () {
            this.update_control_panel({
                breadcrumbs: this.getParent().get_breadcrumbs(),
                cp_content: this.cp_content,
            });
        },
    });

    return DocumentBackend;
});

odoo.define('website_sign.document_edition', function(require) {
    'use strict';

    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var session = require('web.session');
    var DocumentBackend = require('website_sign.DocumentBackend');
    var website_sign_utils = require('website_sign.utils');

    var _t = core._t;

    var AddFollowersDialog = Dialog.extend({
        template: "website_sign.add_followers_dialog",

        init: function(parent, requestID, options) {
            var self = this;
            options = (options || {});
            options.title = options.title || _t("Send a copy to third parties");
            options.size = options.size || "medium";

            if(!options.buttons) {
                options.buttons = [];

                options.buttons.push({text: _t("Send"), classes: "btn-primary", click: function(e) {
                    var $button = $(e.target);
                    $button.prop('disabled', true);

                    website_sign_utils.processPartnersSelection(this.$select).then(function(partners) {
                        self._rpc({
                                model: 'signature.request',
                                method: 'add_followers',
                                args: [self.requestID, partners],
                            })
                            .then(function() {
                                self.do_notify(_t("Success"), _t("A copy has been sent to the new followers."));
                            })
                            .always(function() {
                                self.close();
                            });
                    });
                }});

                options.buttons.push({text: _t("Discard"), close: true});
            }

            this._super(parent, options);

            this.requestID = requestID;
        },

        start: function() {
            this.$select = this.$('#o_sign_followers_select');
            website_sign_utils.setAsPartnerSelect(this.$select);
            return this._super.apply(this, arguments);
        },
    });

    var EditableDocumentBackend = DocumentBackend.extend({
        events: {
            'click .o_sign_resend_access_button.fa': function(e) {
                var $envelope = $(e.target);
                $envelope.removeClass('fa fa-envelope').html('...');
                this._rpc({
                        model: 'signature.request.item',
                        method: 'resend_access',
                        args: [parseInt($envelope.parent('.o_sign_signer_status').data('id'))],
                    })
                    .then(function() { $envelope.html(_t("Resent !")); });
            },
        },

        init: function(parent, options) {
            this._super.apply(this, arguments);

            var self = this;

            this.is_author = (this.create_uid === session.uid);
            this.is_sent = (this.state === 'sent');

            if (options && options.context && options.context.sign_token) {
                var $signButton = $('<button/>', {html: _t("Sign Document"), type: "button", 'class': 'btn btn-sm btn-primary'});
                $signButton.on('click', function () {
                    self.do_action({
                        type: "ir.actions.client",
                        tag: 'website_sign.SignableDocument',
                        name: _t('Sign'),
                    }, {
                        additional_context: _.extend({}, options.context, {
                            token: options.context.sign_token,
                        }),
                    });
                });
                this.cp_content.$buttons = $signButton.add(this.cp_content.$buttons);
            }

            if (this.is_author) {
                var $addFollowersButton = $('<button/>', {html: _t("Send a copy"), type: "button", 'class': 'btn btn-sm btn-default'});
                $addFollowersButton.on('click', function () {
                    (new AddFollowersDialog(self, self.documentID)).open();
                });
                this.cp_content.$buttons = this.cp_content.$buttons.add($addFollowersButton);

                if(this.is_sent) {
                    var $cancelButton = $('<button/>', {html: _t("Cancel Request"), type: "button", 'class': 'btn btn-sm btn-default'});
                    $cancelButton.on('click', function() {
                        self._rpc({
                                model: 'signature.request',
                                method: 'cancel',
                                args: [self.documentID],
                            })
                            .then(function() {
                                self.go_back_to_kanban();
                            });
                    });
                    this.cp_content.$buttons = this.cp_content.$buttons.add($cancelButton);
                }
            }
        },

        start: function() {
            var self = this;

            return this._super.apply(this, arguments).then(function () {
                if(self.is_author && self.is_sent) {
                    self.$('.o_sign_signer_status').each(function(i, el) {
                        $(el).prepend($('<button/>', {
                            type: 'button',
                            title: _t("Resend the invitation"),
                        }).addClass('o_sign_resend_access_button btn btn-link fa fa-envelope pull-right'));
                    });
                }
            });
        },
    });

    core.action_registry.add('website_sign.Document', EditableDocumentBackend);
});

odoo.define('website_sign.document_signing_backend', function(require) {
    'use strict';

    var core = require('web.core');
    var DocumentBackend = require('website_sign.DocumentBackend');
    var document_signing = require('website_sign.document_signing');

    var _t = core._t;

    var NoPubThankYouDialog = document_signing.ThankYouDialog.extend({
        template: "website_sign.no_pub_thank_you_dialog",

        init: function (parent, options) {
            options = (options || {});
            if (!options.buttons) {
                options.buttons = [{text: _t("Ok"), close: true}];
            }

            this._super(parent, options);
        },

        on_closed: function () {
            return this.do_action("website_sign.signature_request_action", {
                clear_breadcrumbs: true,
            });
        },
    });

    var SignableDocument2 = document_signing.SignableDocument.extend({
        get_thankyoudialog_class: function () {
            return NoPubThankYouDialog;
        },
    });

    var SignableDocumentBackend = DocumentBackend.extend({
        get_document_class: function () {
            return SignableDocument2;
        },
    });

    core.action_registry.add('website_sign.SignableDocument', SignableDocumentBackend);
});
