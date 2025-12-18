# Accounting/dashboard/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
import jdatetime


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(default='avatars/default.svg', upload_to='avatars/')
    theme = models.CharField(max_length=10, default='dark')

    def __str__(self):
        return f'{self.user.username} Profile'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class Expense(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Creator Admin"))
    spending_date = models.DateField(verbose_name=_("Spending Date (Shamsi)"), null=True, blank=True)
    issue = models.CharField(max_length=200, verbose_name=_("Issue"), blank=True)
    description = models.TextField(verbose_name=_("Description"), blank=True)
    price = models.PositiveIntegerField(default=0, verbose_name=_("Price"))
    is_server_cost = models.BooleanField(default=False, verbose_name=_("Is it a server cost?"))
    created_at = models.DateTimeField(auto_now_add=True)

    source_bank = models.ForeignKey(
        'BankAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Source Bank"),
        related_name='expenses'
    )

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
    price = models.PositiveIntegerField(default=0, verbose_name=_("Price"))
    created_at = models.DateTimeField(auto_now_add=True)
    destination_bank = models.ForeignKey(
        'BankAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Destination Bank"),
        related_name='other_incomes'
    )

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


class CustomerProfile(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Creator Admin"))
    name = models.CharField(max_length=100, verbose_name=_("Full Name"))
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Phone Number"))

    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_("Introduced by"),
        related_name='introduced_customers'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Customer Profile")
        verbose_name_plural = _("Customer Profiles")
        unique_together = ('creator', 'name')

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Creator Admin"))
    bank_name = models.CharField(max_length=50, verbose_name=_("Bank Name"))
    account_number = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Account Number"))

    class Meta:
        verbose_name = _("Bank Account")
        verbose_name_plural = _("Bank Accounts")
        unique_together = ('creator', 'bank_name')

    def __str__(self):
        return self.bank_name


class Subscription(models.Model):
    STATUS_CHOICES = [('success', _('Paid')), ('pending', _('Unpaid'))]

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='subscriptions',
                                 verbose_name=_("Customer"))
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Creator Admin"))
    year = models.PositiveIntegerField(verbose_name=_("Year (Shamsi)"))
    month = models.PositiveIntegerField(verbose_name=_("Month (Shamsi)"))
    price = models.PositiveIntegerField(default=0, verbose_name=_("Price"))
    giga = models.PositiveIntegerField(default=0, verbose_name=_("Giga"))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name=_("Paid Status"))
    payment_date = models.DateField(null=True, blank=True, verbose_name=_("Payment Date (Shamsi)"))
    expire_date = models.DateField(null=True, blank=True, verbose_name=_("Expiration Date (Gregorian)"))

    referrer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_("Service Referrer"),
        related_name='referred_subscriptions'
    )

    destination_bank = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True,
                                         verbose_name=_("Destination Bank"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")
        # unique_together = ('customer', 'year', 'month') # This line is removed to allow multiple subscriptions
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.customer.name} - {self.year}/{self.month}"

    @property
    def jalali_payment_date(self):
        if self.payment_date:
            return jdatetime.date.fromgregorian(date=self.payment_date).strftime('%Y/%m/%d')
        return _("Not Set")