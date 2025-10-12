from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import Customer, Expense, OtherIncome, Profile
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget


# ویجت سفارشی برای سوییچ (Toggle Switch)
class ToggleSwitchWidget(forms.CheckboxInput):
    pass


# ویجت سفارشی برای کلید وضعیت
class StatusToggleSwitchWidget(forms.CheckboxInput):
    def __init__(self, attrs=None, check_test=None):
        super().__init__(attrs, check_test)
        self.attrs.pop('type', None)

    def get_context(self, name, value, attrs):
        if value == 'success':
            attrs['checked'] = True
        else:
            attrs.pop('checked', None)
        return super().get_context(name, value, attrs)

    def value_from_datadict(self, data, files, name):
        if name in data:
            return 'success'
        return 'pending'


class CustomerForm(forms.ModelForm):
    payment_date = JalaliDateField(widget=AdminJalaliDateWidget(attrs={'class': 'form-input'}),
                                   label=_("Payment Date (Shamsi)"), required=False)
    expire_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
                                  label=_("Expiration Date (Gregorian)"), required=False)

    # FINAL FIX: Explicitly define the status field to ensure it's not required
    status = forms.CharField(required=False, widget=StatusToggleSwitchWidget())

    class Meta:
        model = Customer
        # Note: 'status' is now defined explicitly above
        fields = ['name', 'expire_date', 'price', 'giga', 'phone_number', 'payment_date', 'status', 'referrer',
                  'bank_name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'price': forms.NumberInput(attrs={'class': 'form-input'}),
            'giga': forms.NumberInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'referrer': forms.TextInput(attrs={'class': 'form-input'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-input'}),
        }
        labels = {
            'status': _('Status'),
            'name': _('Full Name'),
            'price': _('Price'),
            'giga': _('Giga'),
            'phone_number': _('Phone Number'),
            'referrer': _('Referrer'),
            'bank_name': _('Bank Name'),
        }


class ExpenseForm(forms.ModelForm):
    spending_date = JalaliDateField(widget=AdminJalaliDateWidget(attrs={'class': 'form-input'}),
                                    label=_("Spending Date (Shamsi)"), required=False)

    class Meta:
        model = Expense
        fields = ['spending_date', 'issue', 'description', 'price', 'is_server_cost']
        widgets = {
            'issue': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'price': forms.NumberInput(attrs={'class': 'form-input'}),
            'is_server_cost': ToggleSwitchWidget(),
        }
        labels = {
            'issue': _('Issue'),
            'description': _('Description'),
            'price': _('Amount'),
            'is_server_cost': _('Is it a server cost?'),
        }


class OtherIncomeForm(forms.ModelForm):
    deposit_date = JalaliDateField(widget=AdminJalaliDateWidget(attrs={'class': 'form-input'}),
                                   label=_("Deposit Date (Shamsi)"), required=False)

    class Meta:
        model = OtherIncome
        fields = ['deposit_date', 'name', 'description', 'price']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'price': forms.NumberInput(attrs={'class': 'form-input'}),
        }
        labels = {
            'name': _('Depositor Name'),
            'description': _('Description'),
            'price': _('Amount'),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
        }
        labels = {
            'first_name': _('First Name'),
            'last_name': _('Last Name'),
            'email': _('Email'),
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'custom-file-input', 'hidden': True}),
        }
        labels = {'avatar': ''}


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget = forms.PasswordInput(attrs={'class': 'form-input'})
        self.fields['old_password'].label = _("Old password")
        self.fields['new_password1'].widget = forms.PasswordInput(attrs={'class': 'form-input'})
        self.fields['new_password1'].label = _("New password")
        self.fields['new_password2'].widget = forms.PasswordInput(attrs={'class': 'form-input'})
        self.fields['new_password2'].label = _("New password confirmation")