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
            'class': 'form-input',
            'placeholder': 'your-username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••••',
        })
    )


# هلپرهای شما (بدون تغییر)
def add_jalali_date_picker_class(field):
    if field:
        existing_classes = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f'{existing_classes} jalali-datepicker'.strip()
        field.widget.attrs['autocomplete'] = 'off'
    return field


def convert_persian_to_english_numbers(text):
    if not isinstance(text, str):
        return text
    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    return text.translate(persian_to_english)


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


# فرم‌های دیگر شما (بدون تغییر)
class UserProfileForm(UserChangeForm):
    # **تغییر اصلی**: اضافه کردن ویجت‌ها برای اعمال کلاس CSS
    username = forms.CharField(label=_("Username"), widget=forms.TextInput(attrs={'class': 'form-input'}))
    first_name = forms.CharField(label=_("First name"), required=False,
                                 widget=forms.TextInput(attrs={'class': 'form-input'}))
    last_name = forms.CharField(label=_("Last name"), required=False,
                                widget=forms.TextInput(attrs={'class': 'form-input'}))
    email = forms.EmailField(label=_("Email address"), widget=forms.EmailInput(attrs={'class': 'form-input'}))

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
    # **تغییر اصلی**: اضافه کردن ویجت سفارشی برای بخش آپلود فایل
    avatar = forms.ImageField(
        label=_("Choose new avatar"),
        required=False,
        widget=forms.FileInput(attrs={'class': 'file-input'})
    )

    class Meta:
        model = Profile
        fields = ['avatar']


class ExpenseForm(forms.ModelForm):
    spending_date = forms.CharField(
        label=_("Spending Date (Shamsi)"),
        required=False,
        widget=forms.TextInput()
    )

    class Meta:
        model = Expense
        fields = ['spending_date', 'issue', 'description', 'price', 'is_server_cost']
        widgets = {
            'issue': forms.TextInput(attrs={'placeholder': _('e.g., Office Rent')}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Any additional details...')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # **تغییر اصلی**: اضافه کردن حلقه برای استایل‌دهی
        for field_name, field in self.fields.items():
            if field_name != 'is_server_cost':  # استایل سوئیچ متفاوت است
                field.widget.attrs.update({'class': 'form-input'})

        add_jalali_date_picker_class(self.fields['spending_date'])
        if self.instance and self.instance.pk and self.instance.spending_date:
            self.initial['spending_date'] = jdatetime.date.fromgregorian(date=self.instance.spending_date).strftime(
                '%Y/%m/%d')

    def clean_spending_date(self):
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

        # **تغییر اصلی**: اضافه کردن حلقه برای استایل‌دهی
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-input'})

        add_jalali_date_picker_class(self.fields['deposit_date'])
        if self.instance and self.instance.pk and self.instance.deposit_date:
            self.initial['deposit_date'] = jdatetime.date.fromgregorian(date=self.instance.deposit_date).strftime(
                '%Y/%m/%d')

    def clean_deposit_date(self):
        date_str = self.cleaned_data.get('deposit_date')
        if date_str:
            return to_gregorian_date(date_str)
        return None


# ===================================================================
# START: CHANGE - کلاس SubscriptionForm شما با استایل‌دهی جدید ادغام شد
# ===================================================================
class SubscriptionForm(forms.ModelForm):
    payment_date = forms.CharField(
        label=_("Payment Date (Shamsi)"),
        required=False,
        widget=forms.TextInput()  # کلاس در __init__ اضافه می‌شود
    )

    class Meta:
        model = Subscription
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

        # **تغییر اصلی**: این حلقه به تمام فیلدهای فرم، کلاس CSS مناسب را اضافه می‌کند
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-input'})

        # استایل‌های خاص همچنان اعمال می‌شوند
        add_jalali_date_picker_class(self.fields.get('payment_date'))
        self.fields['expire_date'].widget.attrs.update({'placeholder': 'YYYY-MM-DD'})

        if self.instance and self.instance.pk and self.instance.payment_date:
            jalali_date = jdatetime.date.fromgregorian(date=self.instance.payment_date)
            self.initial['payment_date'] = jalali_date.strftime('%Y/%m/%d')

    def clean_payment_date(self):
        date_str = self.cleaned_data.get('payment_date')
        if date_str:
            return to_gregorian_date(date_str)
        return None


# END: CHANGE

# فرم‌های پایانی شما (بدون تغییر)
class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = ['name', 'phone_number', 'referred_by']
        # **تغییر**: اضافه کردن placeholder برای راهنمایی بهتر کاربر
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('e.g., John Doe')}),
            'phone_number': forms.TextInput(attrs={'placeholder': _('e.g., 09123456789')}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # **تغییر اصلی**: اضافه کردن کلاس‌های CSS مدرن به هر فیلد
        self.fields['name'].widget.attrs.update({'class': 'form-input'})
        self.fields['phone_number'].widget.attrs.update({'class': 'form-input'})
        self.fields['referred_by'].widget.attrs.update({'class': 'form-select'})

        if user:
            queryset = CustomerProfile.objects.filter(creator=user)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            self.fields['referred_by'].queryset = queryset


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['bank_name', 'account_number']
        # **تغییر**: اضافه کردن placeholder برای راهنمایی بهتر کاربر
        widgets = {
            'bank_name': forms.TextInput(attrs={'placeholder': _('e.g., Bank Melli')}),
            'account_number': forms.TextInput(attrs={'placeholder': _('Optional')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # **تغییر اصلی**: اضافه کردن کلاس CSS مدرن به هر فیلد
        self.fields['bank_name'].widget.attrs.update({'class': 'form-input'})
        self.fields['account_number'].widget.attrs.update({'class': 'form-input'})