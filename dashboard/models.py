from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
import jdatetime


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(default='avatars/default.svg', upload_to='avatars/')
    # فیلد جدید برای ذخیره تم کاربر
    theme = models.CharField(max_length=10, default='dark')  # 'dark' or 'light'

    def __str__(self):
        return f'{self.user.username} Profile'


# --- سیگنال‌ها ---
# وقتی یک کاربر جدید ساخته می‌شود، به صورت خودکار یک پروفایل برای او ایجاد می‌شود.
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # از hasattr برای جلوگیری از خطا در زمان ساخت اولین superuser استفاده می‌کنیم
    if hasattr(instance, 'profile'):
        instance.profile.save()


# ------------------------------------

class Customer(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Creator Admin"))
    name = models.CharField(max_length=100, verbose_name=_("Full Name"))
    expire_date = models.DateField(verbose_name=_("Expiration Date (Gregorian)"), null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name=_("Price"))
    giga = models.PositiveIntegerField(verbose_name=_("Giga"))
    phone_number = models.CharField(max_length=15, verbose_name=_("Phone Number"), blank=True)
    payment_date = models.DateField(verbose_name=_("Payment Date (Shamsi)"), null=True, blank=True)
    is_paid = models.BooleanField(default=False, verbose_name=_("Paid Status"))
    referrer = models.CharField(max_length=100, verbose_name=_("Referrer"), blank=True)
    bank_name = models.CharField(max_length=50, verbose_name=_("Bank Name"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def jalali_payment_date(self):
        if self.payment_date:
            try:
                return jdatetime.date.fromgregorian(date=self.payment_date).strftime('%Y/%m/%d')
            except (ValueError, TypeError):
                return _("Invalid Format")
        return _("Not Set")

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        ordering = ['-created_at']


class Expense(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Creator Admin"))
    spending_date = models.DateField(verbose_name=_("Spending Date (Shamsi)"), null=True, blank=True)
    issue = models.CharField(max_length=200, verbose_name=_("Issue"), blank=True)
    description = models.TextField(verbose_name=_("Description"), blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name=_("Amount"), null=True, blank=True)
    is_server_cost = models.BooleanField(default=False, verbose_name=_("Is it a server cost?"))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.issue or _("Expense without issue")

    @property
    def jalali_spending_date(self):
        if self.spending_date:
            return jdatetime.date.fromgregorian(date=self.spending_date).strftime('%Y/%m/%d')
        return _("Not Set")

    class Meta:
        verbose_name = _("Expense")
        verbose_name_plural = _("Expenses")
        ordering = ['-spending_date']


class OtherIncome(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Creator Admin"))
    deposit_date = models.DateField(verbose_name=_("Deposit Date (Shamsi)"), null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name=_("Depositor Name"), blank=True)
    description = models.TextField(verbose_name=_("Description"), blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name=_("Amount"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or _("Income without name")

    @property
    def jalali_deposit_date(self):
        if self.deposit_date:
            return jdatetime.date.fromgregorian(date=self.deposit_date).strftime('%Y/%m/%d')
        return _("Not Set")

    class Meta:
        verbose_name = _("Other Income")
        verbose_name_plural = _("Other Incomes")
        ordering = ['-deposit_date']

