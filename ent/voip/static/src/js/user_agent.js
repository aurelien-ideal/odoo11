odoo.define('voip.user_agent', function (require) {
"use strict";

var ajax = require('web.ajax');
var Class = require('web.Class');
var core = require('web.core');
var Dialog = require('web.Dialog');
var mixins = require('web.mixins');
var ServicesMixin = require('web.ServicesMixin');

var _t = core._t;

var UserAgent = Class.extend(mixins.EventDispatcherMixin, ServicesMixin, {
    /**
     * @constructor
     */
    init: function (parent) {
        mixins.EventDispatcherMixin.init.call(this);
        this.setParent(parent);
        this.onCall = false;
        ajax.rpc('/web/dataset/call_kw/voip.configurator/get_pbx_config', {
            model: 'voip.configurator',
            method: 'get_pbx_config',
            args: [],
            kwargs: {},
        }).then(this._initUa.bind(this));
        this.blocked = false;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Hangs up the current call.
     */
    hangup: function () {
        if (this.mode === "demo") {
            if (this.onCall) {
                this._onBye();
            } else {
                this._onCancel();
            }
        }
        if (this.sipSession) {
            if (this.onCall === 'ringing') {
                this.sipSession.cancel();
            } else {
                this.sipSession.bye();
            }
        }
    },
    /**
     * Instantiates a new sip call.
     *
     * @param {string} number
     */
    makeCall: function (number) {
        if (this.mode === "demo") {
            var response = {'reason_phrase': "Ringing"};
            var self = this;
            this.trigger_up('sip_ringing');
            this.ringbacktone.play();
            this.timerAccepted = setTimeout(function(){
                self._onAccepted(response);
            },3000);
            // this.timerBye = setTimeout(function(){
            //     self.bye();
            // },10000);
            return;
        }

        //if there is already a media stream, it is reused
        if (this.mediaStream) {
            this._makeCall(number);
        } else {
            if (SIP.WebRTC.isSupported()) {
                /*
                    WebRTC method to get a media stream.
                    The callbacks functions are getUserMediaSuccess, when the function succeed
                    and getUserMediaFailure when the function failed.
                    The _.bind is used to be ensure that the "this" in the callback function will still be the same
                    and not become the object "window".
                */
                var mediaConstraints = {
                    audio: true,
                    video: false
                };
                SIP.WebRTC.getUserMedia(mediaConstraints, _.bind(mediaStreamSuccess,this), _.bind(mediaStreamFailure,this));
            } else {
                this._triggerError(_t('Your browser could not support WebRTC. Please check your configuration.'));
            }
        }
        function mediaStreamSuccess (stream) {
            this.mediaStream = stream;
            this._makeCall(number);
        }
        function mediaStreamFailure (e) {
            this._triggerError(_t('Problem during the connection. Check if the application is allowed to access your microphone from your browser.'), true);
            console.error('getUserMedia failed:', e);
        }
    },
    /**
     * Mutes the current call
     */
    muteCall: function () {
        if (this.sipSession) {
            this.sipSession.mute();
        }
    },
    /**
     * Sends dtmf, when there is a click on keypad number.
     *
     * @param {string} number number clicked
     */
    sendDtmf: function (number) {
        if (this.sipSession) {
            this.sipSession.dtmf(number);
        }
    },
    /**
     * Transfers the call to the given number.
     *
     * @param {string} number
     */
    transfer: function (number) {
        if (this.sipSession) {
            this.sipSession.refer(number);
        }
    },
    /**
     * Unmutes the current call
     */
    unmuteCall: function () {
        if (this.sipSession) {
            this.sipSession.unmute();
        }
    },
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Returns the ua after initialising it.
     *
     * @private
     * @param {Object} params user and pbx configuration parameters
     * @return {Object} the initialised ua
     */
    _createUa: function (params) {
        if (!(params.login && params.pbx_ip && params.password)) {
            this._triggerError(_t('One or more parameter is missing. Please check your configuration.'));
            return false;
        }
        var uaConfig = this._getUaConfig(params);
        try {
            var ua = new SIP.UA(uaConfig);
            return ua;
        } catch (err) {
            this._triggerError(_t('The server configuration could be wrong. Please check your configuration.'));
        }
    },
    /**
     * Returns the ua configuration required.
     *
     * @private
     * @param {Object} params user and pbx configuration parameters
     * @return {Object} the ua configuration parameters
     */
    _getUaConfig: function (params) {
        return {
            uri: params.login + '@' + params.pbx_ip,
            wsServers: params.wsServer || null,
            authorizationUser: params.login,
            password: params.password,
            hackIpInContact: true,
            log: {builtinEnabled: false},
            // log: {level: 'debug'},
            // traceSip: true,
        };
    },
    /**
     * Initialises the ua, binds events and appends audio in the dom.
     *
     * @private
     * @param {Object} result user and pbx configuration return by the rpc
     */
    _initUa: function (result) {
        this.mode = result.mode;
        if (this.mode === "prod") {
            var self = this;
            this.ua = this._createUa(result);
            if (! this.ua) {
                return;
            }
            this.alwaysTransfer = result.always_transfer;
            this.ignoreIncoming = result.ignore_incoming;
            this.externalPhone = result.external_phone;
            // catch the error if the ws uri is wrong
            this.ua.transport.ws.onerror = function () {
                self._triggerError(_t('The websocket uri could be wrong.') +
                    _t(' Please check your configuration.'));
            };
            this.ua.on('invite', _.bind(this._onInvite,this));
        }
        this.remoteAudio = document.createElement("audio");
        this.remoteAudio.autoplay = "autoplay";
        $("html").append(this.remoteAudio);
        this.ringbacktone = document.createElement("audio");
        this.ringbacktone.loop = "true";
        this.ringbacktone.src = "/voip/static/src/sounds/ringbacktone.mp3";
        $("html").append(this.ringbacktone);
        this.incomingtone = document.createElement("audio");
        this.incomingtone.loop = "true";
        this.incomingtone.src = "/voip/static/src/sounds/incomingcall.mp3";
        $("html").append(this.incomingtone);
    },
    /**
     * Triggers the sip invite and binds event on the sip session.
     *
     *  @param {String} number
     *  @private
     */
    _makeCall: function (number) {
        if (this.sipSession) {
            return;
        }
        var callOptions = {
            media: {
                stream: this.mediaStream,
                render: {
                    remote: this.remoteAudio
                }
            }
        };
        try {
            if(this.alwaysTransfer){
                this.sipSession = this.ua.invite(this.externalPhone, callOptions);
                this.currentNumber = number;
            } else {
                this.sipSession = this.ua.invite(number, callOptions);
            }
        } catch (err) {
            this._triggerError(_t('the connection cannot be made. ') +
                _t('Please check your configuration.</br> (Reason receives :') +
                err.reason_phrase + ')');
            return;
        }
        //Bind action when the call is answered
        this.sipSession.on('accepted',_.bind(this._onAccepted,this));
        //Bind action when the call is in progress to catch the ringing phase
        this.sipSession.on('progress', _.bind(this._onProgress,this));
        //Bind action when the call is rejected by the customer
        this.sipSession.on('rejected',_.bind(this._onRejected,this));
        //Bind action when the user hangup the call while ringing
        this.sipSession.on('cancel',_.bind(this._onCancel,this));
        //Bind action when the call is hanged up
        this.sipSession.on('bye',_.bind(this._onBye,this));
    },
    // TODO when the _sendNotification is moved into utils instead of mail.utils
    // remove this function and use the one in utils
    _sendNotification: function (title, content) {
        if (window.Notification && Notification.permission === "granted") {
            return new Notification(title,
                {body: content, icon: "/mail/static/src/img/odoo_o.png", silent: true});
        }
    },
    /**
     * Triggers up an error.
     *
     * @private
     * @param {string} msg message diplayed
     * @param {boolean} temporary if the message can be discarded or not
     */
    _triggerError: function (msg, temporary) {
        this.trigger_up('sip_error', {msg:msg, temporary:temporary});
        this.blocked = true;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Triggered when the call is answered.
     *
     * @private
     */
    _onAccepted: function () {
        this.onCall = true;
        this.ringbacktone.pause();
        this.trigger_up('sip_accepted');
        if(this.alwaysTransfer && this.currentNumber){
            this.sipSession.refer(this.currentNumber);
        }
    },
    /**
     * Handles the sip session ending.
     *
     * @private
     */
    _onBye: function () {
        this.sipSession = false;
        this.onCall = false;
        this.trigger_up('sip_bye');
        if (this.mode === "demo") {
            clearTimeout(this.timerBye);
        }
    },
    /**
     * Handles the sip session cancel.
     *
     * @private
     */
    _onCancel: function () {
        this.sipSession = false;
        this.onCall = false;
        this.ringbacktone.pause();
        this.trigger_up('sip_cancel');
        if (this.mode === "demo") {
            clearTimeout(this.timerAccepted);
            clearTimeout(this.timerBye);
        }
    },
    /**
     * Handles the invite event.
     *
     * @param {Object} inviteSession
     */
    _onInvite: function (inviteSession) {
        if (this.ignoreIncoming) {
            inviteSession.reject();
            return;
        }
        var self = this;
        var name = inviteSession.remoteIdentity.displayName;
        var number = inviteSession.remoteIdentity.uri.user;
        this._rpc({
            model: 'res.partner',
            method: 'search_read',
            domain: [
                '|',
                ['sanitized_phone', 'ilike', number],
                ['sanitized_mobile', 'ilike', number],
            ],
            fields: ['id', 'display_name'],
            limit: 1,
        }).then(function (contacts) {
            var incomingCallParams = {
                number: number
            };
            var contact = false;
            if (contacts.length) {
                contact = contacts[0];
                name = contact.display_name;
                incomingCallParams.partnerId = contact.id;
            }
            var content = _t("Incoming call from ");
            if (name) {
                content += name + ' (' + number + ')';
            } else {
                content += number;
            }
            self.incomingtone.currentTime = 0;
            self.incomingtone.play();

            self.notification = self._sendNotification('Odoo', content);
            function _rejectInvite () {
                if (!self.incomingCall) {
                    self.incomingtone.pause();
                    inviteSession.reject();
                }
            }
            inviteSession.on('rejected', function () {
                if (self.notification) {
                    self.notification.removeEventListener('close', _rejectInvite);
                    self.notification.close('rejected');
                    self.notification = undefined;
                    self.incomingtone.pause();
                } else if (self.dialog.$el.is(":visible")){
                    self.dialog.close();
                }
            });
            if (self.notification) {
                self.notification.onclick = function () {
                    window.focus();
                    var callOptions = {
                        media: {
                            render: {
                                remote: self.remoteAudio
                            }
                        }
                    };
                    inviteSession.accept(callOptions);
                    self.onCall = true;
                    self.incomingCall = true;
                    self.sipSession = inviteSession;
                    self.trigger_up('sip_incoming_call', incomingCallParams);
                    self.incomingtone.pause();
                    //Bind action when the call is hanged up
                    inviteSession.on('bye', _.bind(self._onBye, self));
                    this.close();
                };
                self.notification.addEventListener('close', _rejectInvite);
            } else {
                var options = {
                    confirm_callback: function () {
                        self.incomingtone.pause();
                        if (self.onCall) {
                            self.hangup();
                        }
                        var callOptions = {
                            media: {
                                render: {
                                    remote: self.remoteAudio
                                }
                            }
                        };
                        inviteSession.accept(callOptions);
                        self.onCall = true;
                        self.sipSession = inviteSession;
                        self.trigger_up('sip_incoming_call', incomingCallParams);
                        //Bind action when the call is hanged up
                        inviteSession.on('bye',_.bind(self._onBye,self));
                    },
                    cancel_callback: function () {
                        inviteSession.reject();
                        self.incomingtone.pause();
                    },
                };
                self.dialog = Dialog.confirm(self, content, options);
                self.dialog.on('closed', self, function () {
                    if (inviteSession) {
                        inviteSession.reject();
                    }
                    self.incomingtone.pause();
                });
            }
        });
    },
    /**
     * Triggered when the call reached the called end and start ringing.
     *
     * @private
     * @param {Object} response
     */
    _onProgress: function (response) {
        // some version of asterisk don't send ringing but trying or both
        if (!this.onCall && (response.reason_phrase === "Ringing" || response.reason_phrase === "Trying")) {
            this.onCall = 'ringing';
            this.trigger_up('sip_ringing');
            this.ringbacktone.play();
        }
    },
    /**
     * Handles the sip session rejection.
     *
     * @private
     * @param {Object} response
     */
    _onRejected: function (response) {
        if (this.sipSession) {
            this.sipSession = false;
            this.onCall = false;
            this.trigger_up('sip_rejected');
            this.sipSession = false;
            this.ringbacktone.pause();
            if (response.status_code === 404 || response.status_code === 488) {
                this._triggerError(
                    _.str.sprintf(_t('The number is incorrect, the user credentials') +
                    _t('could be wrong or the connection cannot be made.') +
                    _t(' Please check your configuration.</br> (Reason receives :%s)',
                        response.reason_phrase)),
                    true);
            }
        }
    },
});

return UserAgent;

});
