from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import Customer, Expense, OtherIncome
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

class CustomerForm(forms.ModelForm):
    payment_date = JalaliDateField(widget=AdminJalaliDateWidget, label=_("Payment Date (Shamsi)"), required=False)
    
    class Meta:
        model = Customer
        fields = ['name', 'expire_date', 'price', 'giga', 'phone_number', 'payment_date', 'is_paid', 'referrer', 'bank_name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'expire_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'price': forms.NumberInput(attrs={'class': 'form-input'}),
            'giga': forms.NumberInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'is_paid': forms.CheckboxInput(attrs={'class': 'h-6 w-6 rounded text-purple-500 focus:ring-purple-600'}),
            'referrer': forms.TextInput(attrs={'class': 'form-input'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-input'}),
        }
        labels = { 
            'is_paid': _('Paid'),
            'name': _('Full Name'),
            'expire_date': _('Expiration Date (Gregorian)'),
            'price': _('Price'),
            'giga': _('Giga'),
            'phone_number': _('Phone Number'),
            'referrer': _('Referrer'),
            'bank_name': _('Bank Name'),
        }

# فرم جدید برای هزینه
class ExpenseForm(forms.ModelForm):
    spending_date = JalaliDateField(widget=AdminJalaliDateWidget, label=_("Spending Date (Shamsi)"), required=False)
    
    class Meta:
        model = Expense
        fields = ['spending_date', 'issue', 'description', 'price', 'is_server_cost']
        widgets = {
            'issue': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-input'}),
            'is_server_cost': forms.CheckboxInput(attrs={'class': 'h-6 w-6 rounded text-purple-500 focus:ring-purple-600'}),
        }
        labels = {
            'issue': _('Issue'),
            'description': _('Description'),
            'price': _('Amount'),
            'is_server_cost': _('Is it a server cost?'),
        }


# فرم جدید برای سایر درآمدها
class OtherIncomeForm(forms.ModelForm):
    deposit_date = JalaliDateField(widget=AdminJalaliDateWidget, label=_("Deposit Date (Shamsi)"), required=False)
    
    class Meta:
        model = OtherIncome
        fields = ['deposit_date', 'name', 'description', 'price']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
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

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget = forms.PasswordInput(attrs={'class': 'form-input'})
        self.fields['old_password'].label = _("Old password")
        self.fields['new_password1'].widget = forms.PasswordInput(attrs={'class': 'form-input'})
        self.fields['new_password1'].label = _("New password")
        self.fields['new_password2'].widget = forms.PasswordInput(attrs={'class': 'form-input'})
        self.fields['new_password2'].label = _("New password confirmation")

