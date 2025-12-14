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
    class Meta:
        model = Subscription
        fields = ['customer', 'year', 'month', 'price', 'giga', 'status', 'payment_date', 'expire_date', 'referrer',
                  'destination_bank']
        widgets = {
            # تبدیل فیلدهای سال و ماه به لیست کشویی (Select)
            'year': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'month': forms.Select(attrs={'class': 'form-select select2-enable'}),

            # بقیه فیلدها
            'price': forms.TextInput(attrs={'class': 'form-input'}),
            'giga': forms.TextInput(attrs={'class': 'form-input'}),
            'payment_date': forms.TextInput(attrs={'class': 'form-input jalali-datepicker', 'autocomplete': 'off'}),
            'expire_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'customer': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'referrer': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'destination_bank': forms.Select(attrs={'class': 'form-select select2-enable'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(SubscriptionForm, self).__init__(*args, **kwargs)

        # 1. تنظیم گزینه‌های سال (از ۵ سال قبل تا ۵ سال بعد)
        this_year = jdatetime.date.today().year
        YEAR_CHOICES = [(y, y) for y in range(this_year - 5, this_year + 5)]
        self.fields['year'].widget.choices = YEAR_CHOICES

        # 2. تنظیم گزینه‌های ماه (نام‌های فارسی/انگلیسی بر اساس ترجمه)
        MONTH_CHOICES = [
            (1, _('Farvardin')), (2, _('Ordibehesht')), (3, _('Khordad')),
            (4, _('Tir')), (5, _('Mordad')), (6, _('Shahrivar')),
            (7, _('Mehr')), (8, _('Aban')), (9, _('Azar')),
            (10, _('Dey')), (11, _('Bahman')), (12, _('Esfand'))
        ]
        self.fields['month'].widget.choices = MONTH_CHOICES

        # 3. فیلتر کردن لیست‌ها بر اساس کاربر لاگین شده
        if self.user:
            self.fields['customer'].queryset = CustomerProfile.objects.filter(creator=self.user)
            self.fields['referrer'].queryset = CustomerProfile.objects.filter(creator=self.user)
            self.fields['destination_bank'].queryset = BankAccount.objects.filter(creator=self.user)


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