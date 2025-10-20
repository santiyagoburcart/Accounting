# Accounting/dashboard/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserChangeForm, PasswordChangeForm
from .models import Expense, OtherIncome, Profile, Subscription, CustomerProfile, BankAccount, User
import jdatetime
from django.core.exceptions import ValidationError

class CustomAuthenticationForm(AuthenticationForm):
    """
    یک فرم لاگین سفارشی که کلاس‌های CSS مدرن را به فیلدها اضافه می‌کند.
    """
    username = forms.CharField(
        label=_("Username"),
        widget=forms.TextInput(attrs={
            'class': 'form-input', # <-- کلاس اصلی برای استایل‌دهی
            'placeholder': 'your-username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-input', # <-- کلاس اصلی برای استایل‌دهی
            'placeholder': '••••••••••',
        })
    )

# هلپر برای افزودن کلاس تقویم شمسی به فیلدهای تاریخ
def add_jalali_date_picker_class(field):
    if field:
        existing_classes = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f'{existing_classes} jalali-datepicker'.strip()
        field.widget.attrs['autocomplete'] = 'off'
    return field


# تابع کمکی برای تبدیل اعداد فارسی به انگلیسی
def convert_persian_to_english_numbers(text):
    if not isinstance(text, str):
        return text
    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    return text.translate(persian_to_english)


# هلپر برای تبدیل تاریخ شمسی به میلادی
def to_gregorian_date(jalali_date_str):
    if not jalali_date_str:
        return None

    english_date_str = convert_persian_to_english_numbers(jalali_date_str)
    english_date_str = english_date_str.strip().replace('-', '/')

    try:
        j_date = jdatetime.datetime.strptime(english_date_str, '%Y/%m/%d').date()
        return j_date.togregorian()
    except (ValueError, TypeError):
        raise ValidationError(_("Invalid date format. Please use YYYY/MM/DD."), code='invalid_date')


class UserProfileForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super(CustomPasswordChangeForm, self).__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-input', 'placeholder': _('Old Password')})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-input', 'placeholder': _('New Password')})
        self.fields['new_password2'].widget.attrs.update(
            {'class': 'form-input', 'placeholder': _('Confirm New Password')})


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']


class ExpenseForm(forms.ModelForm):
    # فیلد تاریخ را به عنوان یک رشته متنی تعریف می‌کنیم تا اعتبارسنجی جنگو را دور بزنیم
    spending_date = forms.CharField(
        label=_("Spending Date (Shamsi)"),
        required=False,
        widget=forms.TextInput()
    )

    class Meta:
        model = Expense
        # با استفاده از 'fields'، کنترل کامل فرم را به دست می‌گیریم
        fields = ['spending_date', 'issue', 'description', 'price', 'is_server_cost']
        widgets = {
            'issue': forms.TextInput(attrs={'placeholder': _('e.g., Office Rent')}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Any additional details...')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_jalali_date_picker_class(self.fields['spending_date'])
        # هنگام ویرایش، تاریخ میلادی را به شمسی تبدیل و در فیلد قرار می‌دهیم
        if self.instance and self.instance.pk and self.instance.spending_date:
            self.initial['spending_date'] = jdatetime.date.fromgregorian(date=self.instance.spending_date).strftime(
                '%Y/%m/%d')

    def clean_spending_date(self):
        # رشته تاریخ شمسی را دریافت و به تاریخ میلادی معتبر تبدیل می‌کنیم
        date_str = self.cleaned_data.get('spending_date')
        if date_str:
            return to_gregorian_date(date_str)
        return None


class OtherIncomeForm(forms.ModelForm):
    deposit_date = forms.CharField(
        label=_("Deposit Date (Shamsi)"),
        required=False,
        widget=forms.TextInput()
    )

    class Meta:
        model = OtherIncome
        fields = ['deposit_date', 'name', 'description', 'price']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _("e.g., Project X Payment")}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Any additional details...')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_jalali_date_picker_class(self.fields['deposit_date'])
        if self.instance and self.instance.pk and self.instance.deposit_date:
            self.initial['deposit_date'] = jdatetime.date.fromgregorian(date=self.instance.deposit_date).strftime(
                '%Y/%m/%d')

    def clean_deposit_date(self):
        date_str = self.cleaned_data.get('deposit_date')
        if date_str:
            return to_gregorian_date(date_str)
        return None


class SubscriptionForm(forms.ModelForm):
    payment_date = forms.CharField(
        label=_("Payment Date (Shamsi)"),
        required=False,
        widget=forms.TextInput()
    )

    class Meta:
        model = Subscription
        # با استفاده از 'fields' به جای 'exclude'، کنترل کامل فرم را به دست می‌گیریم
        fields = [
            'customer', 'year', 'month', 'price', 'giga', 'status',
            'payment_date', 'expire_date', 'referrer', 'destination_bank'
        ]
        widgets = {
            'expire_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['customer'].queryset = CustomerProfile.objects.filter(creator=user)
            self.fields['referrer'].queryset = CustomerProfile.objects.filter(creator=user)
            self.fields['destination_bank'].queryset = BankAccount.objects.filter(creator=user)

        add_jalali_date_picker_class(self.fields.get('payment_date'))
        self.fields['expire_date'].widget.attrs.update({'class': 'form-input', 'placeholder': 'YYYY-MM-DD'})

        if self.instance and self.instance.pk and self.instance.payment_date:
            jalali_date = jdatetime.date.fromgregorian(date=self.instance.payment_date)
            self.initial['payment_date'] = jalali_date.strftime('%Y/%m/%d')

    def clean_payment_date(self):
        date_str = self.cleaned_data.get('payment_date')
        if date_str:
            return to_gregorian_date(date_str)
        return None


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = ['name', 'phone_number', 'referred_by']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            queryset = CustomerProfile.objects.filter(creator=user)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            self.fields['referred_by'].queryset = queryset


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['bank_name', 'account_number']