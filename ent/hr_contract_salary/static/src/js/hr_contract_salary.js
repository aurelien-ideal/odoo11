odoo.define('hr_contract_salary', function (require) {
"use strict";

var ajax = require('web.ajax');
var base = require('web_editor.base');
var Widget = require('web.Widget');
var core = require('web.core');
var _t = core._t;

var SalaryPackageWidget = Widget.extend({
    template: 'hr_contract_salary.salary_package',
    events: {
        "change .advantage_input": "onchange_advantage",
        "change input[name='mobility']": "onchange_mobility",
        "change input[name='representation_fees_radio']": "onchange_representation_fees",
        "change input[name='fuel_card_slider']": "onchange_fuel_card",
        "input input[name='holidays_slider']": "onchange_holidays",
        "change input[name='mobile']": "onchange_mobile",
        "change input[name='mobile-ic']": "onchange_mobile",
        "change input[name='internet']": "onchange_internet",
        "change select[name='select_car']": "onchange_car_id",
        "change input[name='public_transport_employee_amount']": "onchange_public_transport",
        "change select[name='marital']": "onchange_marital",
        "change select[name='spouse_fiscal_status']": "onchange_spouse_fiscal_status",
        "change input[name='disabled_children']": "onchange_disabled_children",
        "change input[name='other_dependent_people']": "onchange_other_dependent_people",
        "click #hr_cs_submit": "submit_salary_package",
        "click button[name='compute_button']": "compute_net",
        "click a[name='recompute']": "recompute",
        "click button[name='toggle_personal_information']": "toggle_personal_information",
    },

    init: function(parent, options) {
        this._super(parent);
        this.update_gross_to_net_computation();
        $("div#company_car select").val() === 'new' ? $("div#new_company_car").removeClass('hidden') : $("div#new_company_car").addClass('hidden')
        var transport_mode = _.find($("input[name='mobility']"), function(transport_mode) {
            return transport_mode.checked;
        }).value;
        this.onchange_mobile();
        this.onchange_internet();
        this.onchange_holidays();
        this.onchange_disabled_children();
        this.onchange_marital();
        this.onchange_spouse_fiscal_status();
        this.onchange_other_dependent_people();
        $('body').attr('id', 'hr_contract_salary');
        $(".mobility-options").addClass('hidden');
        $(".mobility-options#" + transport_mode).removeClass('hidden');
        $("a[name='recompute']").addClass("hidden");
        $("#hr_contract_salary select").select2({
            minimumResultsForSearch: -1
        });
        $('b[role="presentation"]').hide();
        $('.select2-arrow').append('<i class="fa fa-chevron-down"></i>');
    },

    get_personal_info: function() {
        return {
            'name': $("input[name='name']").val(),
            'gender': _.find($("input[name='gender']"), function(gender) {
                return gender.checked;
            }).value,
            'disabled': $("input[name='disabled']")[0].checked,
            'marital': $("select[name='marital']").val(),
            'spouse_fiscal_status': $("select[name='spouse_fiscal_status']").val(),
            'spouse_net_revenue': parseFloat($("input[name='spouse_net_revenue']").val()) || 0.0,
            'spouse_other_net_revenue': parseFloat($("input[name='spouse_other_net_revenue']").val()) || 0.0,
            'disabled_spouse_bool': $("input[name='disabled_spouse_bool']")[0].checked,
            'children_count': parseInt($("input[name='children_count']").val()) || 0,
            'disabled_children': $("input[name='disabled_children']")[0].checked,
            'disabled_children_count': parseInt($("input[name='disabled_children_count']").val()) || 0,
            'other_dependent_people': $("input[name='other_dependent_people']")[0].checked,
            'other_senior_dependent': parseInt($("input[name='other_senior_dependent']").val()) || 0,
            'other_disabled_senior_dependent': parseInt($("input[name='other_disabled_senior_dependent']").val()) || 0,
            'other_juniors_dependent': parseInt($("input[name='other_juniors_dependent']").val()) || 0,
            'other_disabled_juniors_dependent': parseInt($("input[name='other_disabled_juniors_dependent']").val()) || 0,
            'birthdate': $("input[name='birthdate']").val(),
            'street': $("input[name='street']").val(), 
            'street2': $("input[name='street2']").val(), 
            'city': $("input[name='city']").val(),
            'zip': $("input[name='zip']").val(),
            'state': $("input[name='state']").val(),
            'country': parseInt($("select[name='country']").val()),
            'email': $("input[name='email']").val(),
            'phone': $("input[name='phone']").val(),
            'national_number': $("input[name='national_number']").val(),
            'nationality': parseInt($("select[name='nationality']").val()),
            'certificate': $("select[name='certificate']").val(),
            'certificate_name': $("input[name='certificate_name']").val(),
            'certificate_school': $("input[name='certificate_school']").val(),
            'bank_account': $("input[name='bank_account']").val(),
            'emergency_info': $("input[name='emergency_info']").val(),
        };
    },

    get_advantages: function() {
        var self = this;
        var has_commission = $("input[name='commission_on_target']").length;
        var has_meal_voucher = $("input[name='meal_voucher_amount']").length;
        var car_value = $("select[name='select_car']").val();
        var car_id = false;
        var new_car = false;
        if (car_value) {
            car_id = parseInt($("select[name='select_car']").val().split('-')[1]);
            if ($("select[name='select_car']").val().split('-')[0] === 'new') {
                new_car = true;
            } else {
                new_car = false;
            }            
        }
        var personal_info = {};
        if ($("input[name='gender']").length) {
            personal_info = self.get_personal_info();
        }
        var advantages = {
            'wage': $("input[name='wage']")[0].value,
            'has_internet': $("input[name='internet']")[0].checked,
            'has_mobile': $("input[name='mobile']")[0].checked,
            'international_communication': $("input[name='mobile-ic']")[0].checked,
            'fuel_card': parseFloat($("input[name='fuel_card_input']")[0].value) || 0.0,
            'transport_mode': _.find($("input[name='mobility']"), function(transport_mode) {
                return transport_mode.checked;
            }).value,
            'car_employee_deduction': parseFloat($("input[name='car_employee_deduction']")[0].value) || 0.0,
            'holidays': parseFloat($("input[name='holidays_slider']")[0].value) || 0.0,
            'commission_on_target': has_commission ? parseFloat($("input[name='commission_on_target']")[0].value) || 0.0 : 0.0,
            'eco_checks': parseFloat($("input[name='eco_checks']")[0].value),
            'representation_fees': parseFloat($("input[name='representation_fees']")[0].value) || 0.0,
            'car_id': car_id,
            'new_car': new_car,
            'requested_model_id': parseInt($('div#new_company_car select').val()),
            'public_transport_employee_amount': parseFloat($("input[name='public_transport_employee_amount']")[0].value) || 0.0,
            'others_reimbursed_amount': parseFloat($("input[name='others_reimbursed_amount']")[0].value) || 0.0,
            'personal_info': personal_info,
            'meal_voucher_amount': has_meal_voucher ? parseFloat($("input[name='meal_voucher_amount']")[0].value) || 0.0 : 0.0,
        };
        return advantages;

    },

    update_gross_to_net_computation: function () {
        ajax.jsonRpc('/salary_package/compute_net/', 'call', {
            'contract_id': parseInt($("input[name='contract']")[0].id),
            'token': $("input[name='token']").val(),
            'advantages': this.get_advantages(),
        }).then(function(data) {
            $("input[name='wage']").val(data['BASIC']);
            $("input[name='wage_with_holidays']").val(data['wage_with_holidays']);
            $("input[name='SALARY']").val(data['SALARY']);
            $("input[name='ONSS']").val(- data['ONSS']);
            $("input[name='GROSS']").val(data['GROSS']);
            $("input[name='P.P']").val(- data['P.P']);
            $("input[name='PP.RED']").val(data['PP.RED']);
            $("input[name='M.ONSS']").val(- data['M.ONSS']);
            $("input[name='EMP.BONUS']").val(data['EMP.BONUS']);
            $("input[name='MEAL_V_EMP']").val(- data['MEAL_V_EMP']);
            $("input[name='ATN.CAR.1']").val(- data['ATN.CAR.2']);
            $("input[name='ATN.INT.1']").val(- data['ATN.INT.2']);
            $("input[name='ATN.MOB.1']").val(- data['ATN.MOB.2']);
            $("input[name='ATN.CAR.2']").val(- data['ATN.CAR.2']);
            $("input[name='ATN.INT.2']").val(- data['ATN.INT.2']);
            $("input[name='ATN.MOB.2']").val(- data['ATN.MOB.2']);
            $("input[name='NET']").val(data['NET']);
            $("input[name='monthly_nature']").val(data['monthly_nature']);
            $("input[name='monthly_cash']").val(data['monthly_cash']);
            $("input[name='yearly_cash']").val(data['yearly_cash']);
            $("input[name='monthly_total']").val(data['monthly_total']);
            $("input[name='employee_total_cost']").val(data['employee_total_cost']);
            $("input[name='holidays_compensation_input']").val(data['holidays_compensation']);
            $("span[name='compensation_amount']").html(data['holidays_compensation']);
            $("input[name='car_employee_deduction']").val(data['company_car_total_depreciated_cost']);
            var mobile_atn_div = $("div[name='mobile_atn']");
            var internet_atn_div = $("div[name='internet_atn']");
            var company_car_atn_div = $("div[name='company_car_atn']");
            var employment_bonus_div = $("div[name='employment_bonus']");
            var withholding_tax_reduction_div = $("div[name='withholding_tax_reduction']");
            var miscellaneous_onss_div = $("div[name='m_onss_div']");
            var representation_fees_div = $("div[name='representation_fees_div']");
            data['ATN.MOB.2'] ? mobile_atn_div.removeClass('hidden') : mobile_atn_div.addClass('hidden');
            data['ATN.INT.2'] ? internet_atn_div.removeClass('hidden') : internet_atn_div.addClass('hidden');
            data['ATN.CAR.2'] ? company_car_atn_div.removeClass('hidden') : company_car_atn_div.addClass('hidden');
            data['EMP.BONUS'] ? employment_bonus_div.removeClass('hidden') : employment_bonus_div.addClass('hidden');
            data['PP.RED'] ? withholding_tax_reduction_div.removeClass('hidden') : withholding_tax_reduction_div.addClass('hidden');
            data['M.ONSS'] ? miscellaneous_onss_div.removeClass('hidden') : miscellaneous_onss_div.addClass('hidden');
            data['REP.FEES'] ? representation_fees_div.removeClass('hidden') : representation_fees_div.addClass('hidden');
            $("div[name='compute_loading']").addClass("hidden");
            $("div[name='net']").removeClass("hidden").hide().slideDown( "slow" );
            $("input[name='NET']").removeClass('o_outdated');
        });
    },

    onchange_advantage: function() {
        var self = this;
        $("div[name='net']").addClass("hidden");
        $("div[name='compute_net']").removeClass("hidden");
        $("a[name='details']").addClass("hidden");
        $("a[name='recompute']").removeClass("hidden");
        $("input[name='NET']").addClass('o_outdated');
        ajax.jsonRpc('/salary_package/update_gross/', 'call', {
            'contract_id': parseInt($("input[name='contract']")[0].id),
            'token': $("input[name='token']").val(),
            'advantages': this.get_advantages(),
        }).then(function(data) {
            $("input[name='wage']").val(data['new_gross']);
            self.compute_net();
        });
    },

    compute_net: function() {
        $("a[name='recompute']").addClass("hidden");
        $("a[name='details']").removeClass("hidden");
        this.update_gross_to_net_computation();
    },

    onchange_mobility: function(event) {
        var transport_mode = event.target.value;
        $(".mobility-options").addClass('hidden');
        $(".mobility-options#" + transport_mode).removeClass('hidden');
        var fuel_card_div = $("div[name='fuel_card']");
        event.target.value === 'company_car' ? fuel_card_div.removeClass("hidden") : fuel_card_div.addClass("hidden");
    },

    onchange_representation_fees: function(event) {
        $("input[name='representation_fees']").val(event.target.value);
    },

    onchange_fuel_card: function(event) {
        $("input[name='fuel_card_input']").val(event.target.value);
    },

    onchange_holidays: function(event) {
        var amount_days = $("input[name='holidays_slider']").val();
        $("input[name='holidays_input']").val(amount_days);
        $("span[name='holidays_amount']").html(amount_days);
        if ($("input[name='holidays_slider']").val() < 20.0) {
            $("div[name='holidays_20_days']").removeClass("hidden");
        } else {
            $("div[name='holidays_20_days']").addClass("hidden");
        }
    },

    // TODO Restring to useful arguments
    onchange_mobile: function(event) {
        var has_mobile = $("input[name='mobile']")[0].checked;
        var tooltip = $("span#mobile_tooltip");
        has_mobile ? tooltip.removeClass("hidden") : tooltip.addClass("hidden");
        var label = $("label[name='international_communication']");
        $("input[name='mobile']")[0].checked ? label.removeClass('invisible') : label.addClass('invisible');
        ajax.jsonRpc('/salary_package/onchange_mobile/', 'call', {
            'contract_id': parseInt($("input[name='contract']")[0].id),
            'advantages': this.get_advantages(),
        }).then(function(data) {
            $("input[name='mobile_amount']").val(data['mobile']);
        });
    },

    onchange_internet: function(event) {
        var has_internet = $("input[name='internet']")[0].checked;
        var tooltip = $("span#internet_tooltip");
        has_internet ? tooltip.removeClass("hidden") : tooltip.addClass("hidden");
        ajax.jsonRpc('/salary_package/onchange_internet', 'call', {
            'contract_id': parseInt($("input[name='contract']")[0].id),
            'advantages': this.get_advantages(),
        }).then(function(data) {
            $("input[name='internet_amount']").val(data['internet']);
        });
    },

    onchange_car_id: function(event) {
        var car_value = $("select[name='select_car']").val();
        var car_option = car_value ? (car_value).split('-')[0] : '';
        if (car_option === 'new') {
            $("span[name='new_car_message']").removeClass('hidden');
        } else {
            $("span[name='new_car_message']").addClass('hidden');
            this.onchange_advantage();
        }
    },

    onchange_public_transport: function(event) {
        ajax.jsonRpc('/salary_package/onchange_public_transport/', 'call', {
            'contract_id': parseInt($("input[name='contract']")[0].id),
            'advantages': this.get_advantages(),
        }).then(function(data) {
            $("input[name='public_transport_reimbursed_amount']").val(data['amount']);
        });
    },

    onchange_marital: function(event) {
        var marital = $("select[name='marital']").val();
        var spouse_info_div = $("div[name='spouse_information']");
        marital === 'married' ? spouse_info_div.removeClass('hidden') : spouse_info_div.addClass('hidden');
    },

    onchange_spouse_fiscal_status: function(event) {
        var fiscal_status = $("select[name='spouse_fiscal_status']").val();
        var spouse_revenue_info_div = $("div[name='spouse_revenue_information']");
        fiscal_status === "with income" ? spouse_revenue_info_div.removeClass("hidden") : spouse_revenue_info_div.addClass("hidden")
    },

    onchange_disabled_children: function(event) {
        var disabled_children = $("input[name='disabled_children']")[0].checked;
        var disabled_children_div = $("div[name='disabled_children_info']");
        disabled_children ? disabled_children_div.removeClass('hidden') : disabled_children_div.addClass('hidden');
    },

    onchange_other_dependent_people: function(event) {
        var other_dependent_people = $("input[name='other_dependent_people']")[0].checked;
        var other_dependent_people_div = $("div[name='other_dependent_people_info']");
        other_dependent_people ? other_dependent_people_div.removeClass('hidden') : other_dependent_people_div.addClass('hidden');
    },

    recompute: function(event) {
        $("a[name='details']").removeClass("hidden");
        $("a[name='recompute']").addClass("hidden");
        $("input[name='NET']").removeClass('o_outdated');
    },

    submit_salary_package: function(event) {
        var required_empty_input = _.find($("input:required"), function(input) {return input.value === ''; });
        var required_empty_select = _.find($("select:required"), function(select) {return $(select).val() === ''; });
        var email = $("input[name='email']").val();
        var atpos = email.indexOf("@");
        var dotpos = email.lastIndexOf(".");
        var invalid_email = atpos<1 || dotpos<atpos+2 || dotpos+2>=email.length;
        if(required_empty_input || required_empty_select) {
            $("button#hr_cs_submit").parent().append("<div class='alert alert-danger alert-dismissable fade in'>" + _('Some required fields are not filled') + "</div>");
            _.each($("input:required"), function(input) {
                if (input.value === '') {
                    $(input).addClass('bg-danger');
                } else {
                    $(input).removeClass('bg-danger');
                }
            });
            _.each($("select:required"), function(select) {
                if ($(select).val() === '') {
                    $(select).parent().addClass('bg-danger');
                } else {
                    $(select).parent().removeClass('bg-danger');
                }
            });
            $("section#hr_cs_personal_information")[0].scrollIntoView({block: "end", behavior: "smooth"});
        }
        if (invalid_email) {
            $("input[name='email']").addClass('bg-danger');
            $("button#hr_cs_submit").parent().append("<div class='alert alert-danger alert-dismissable fade in'>" + _('Not a valid e-mail address') + "</div>");
            $("section#hr_cs_personal_information")[0].scrollIntoView({block: "end", behavior: "smooth"});
        } else {
            $("input[name='email']").removeClass('bg-danger');
        }
        $(".alert").delay(4000).slideUp(200, function() {
            $(this).alert('close');
        });
        if (!invalid_email && !required_empty_input && !required_empty_select) {
            ajax.jsonRpc('/salary_package/submit/', 'call', {
                'contract_id': parseInt($("input[name='contract']")[0].id),
                'token': $("input[name='token']").val(),
                'advantages': this.get_advantages(),
            }).then(function (data) {
                if (data['error']) {
                    $("button#hr_cs_submit").parent().append("<div class='alert alert-danger alert-dismissable fade in'>" + data['error_msg'] + "</div>");
                } else {
                    document.location.pathname = '/sign/document/' + data['request_id'] + '/' + data['token'];
                }
            });
        }
    },

    toggle_personal_information: function() {
        $("button[name='toggle_personal_information']").toggleClass('hidden');
        $("div[name='personal_info']").toggle(500);
    }

});

base.ready().done(function() {
    if ($('#hr_cs_form').length > 0) {
        var salary_package_widget = new SalaryPackageWidget();
        salary_package_widget.attachTo($('#hr_cs_form').first());
    }
});

return SalaryPackageWidget;
});
