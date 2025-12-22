import os
import subprocess
import requests
import gzip
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils.translation import gettext as _
from django.urls import reverse_lazy, reverse
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from itertools import chain
from operator import attrgetter
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.template.defaulttags import register
import jdatetime
import pandas as pd
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# بقیه ایمپورت‌ها مثل قبل (Sum, chain, timezone, render, etc.)
from dashboard.forms.mobile_forms import MobileAuthenticationForm

# وارد کردن مدل‌ها و فرم‌های خودتان
from dashboard.forms import (
    UserProfileForm, CustomPasswordChangeForm, ExpenseForm,
    OtherIncomeForm, ProfileUpdateForm, SubscriptionForm, CustomerProfileForm,
    BankAccountForm, CustomAuthenticationForm
)
from dashboard.models import (
    Expense, OtherIncome, Profile, Subscription, CustomerProfile,
    BankAccount
)

from dashboard.views.mobile import mobile_home_view, mobile_add_transaction_view  # <--- این را اضافه کن


# ===================================================================
# تنظیمات سیستم بک‌آپ (از متغیرهای محیطی)
# ===================================================================
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_HOST = os.environ.get('DB_HOST', 'db')  # نام سرویس دیتابیس در docker-compose
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')


@register.filter
def class_name(value):
    return value.__class__.__name__



def is_mobile(request):
    """ تشخیص ساده موبایل از روی User-Agent """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    mobile_agents = ['mobile', 'android', 'iphone', 'ipad', 'phone']
    return any(agent in user_agent for agent in mobile_agents)


class CustomLoginView(LoginView):
    template_name = 'dashboard/desktop/login.html'  # پیش‌فرض دسکتاپ
    redirect_authenticated_user = True
    authentication_form = CustomAuthenticationForm  # پیش‌فرض دسکتاپ

    def get_template_names(self):
        # اگر موبایل بود، قالب موبایل را برگردان
        if getattr(self.request, 'is_mobile', False):
            return ['dashboard/mobile/login.html']
        return [self.template_name]

    def get_form_class(self):
        # اگر موبایل بود، فرم موبایل را استفاده کن
        if getattr(self.request, 'is_mobile', False):
            return MobileAuthenticationForm
        return self.authentication_form


# ===================================================================
# START: ویو تراکنش‌ها
# ===================================================================
@login_required
def add_transaction_view(request):

    
    if getattr(request, 'is_mobile', False):
        return mobile_add_transaction_view(request)
    """
    داشبورد مدیریت تراکنش‌ها: شامل فرم‌های ورود اطلاعات و نمایش آمار ماهانه.
    """
    expense_form = ExpenseForm(prefix='expense')
    other_income_form = OtherIncomeForm(prefix='income')

    redirect_url = reverse_lazy('dashboard:add_transaction')
    if request.GET.get('year') and request.GET.get('month'):
        redirect_url += f"?year={request.GET.get('year')}&month={request.GET.get('month')}"

    if request.method == 'POST':
        if 'add_expense' in request.POST:
            form_to_validate = ExpenseForm(request.POST, prefix='expense')
            if form_to_validate.is_valid():
                expense = form_to_validate.save(commit=False)
                expense.creator = request.user
                expense.save()
                messages.success(request, _("Expense added successfully."))
                return redirect(redirect_url)
            else:
                expense_form = form_to_validate

        elif 'add_other_income' in request.POST:
            form_to_validate = OtherIncomeForm(request.POST, prefix='income')
            if form_to_validate.is_valid():
                income = form_to_validate.save(commit=False)
                income.creator = request.user
                income.save()
                messages.success(request, _("Income added successfully."))
                return redirect(redirect_url)
            else:
                other_income_form = form_to_validate

    today_jalali = jdatetime.date.today()
    selected_year = request.GET.get('year', str(today_jalali.year))
    selected_month = request.GET.get('month', str(today_jalali.month))

    expenses_base = Expense.objects.filter(creator=request.user)
    other_incomes_base = OtherIncome.objects.filter(creator=request.user)

    year, month = int(selected_year), int(selected_month)
    start_date_jalali = jdatetime.date(year, month, 1)
    days_in_month = 31 if month < 7 else (30 if month < 12 else (30 if start_date_jalali.isleap() else 29))
    end_date_jalali = jdatetime.date(year, month, days_in_month)
    start_gregorian = start_date_jalali.togregorian()
    end_gregorian = end_date_jalali.togregorian()

    expenses_in_month = expenses_base.filter(spending_date__range=[start_gregorian, end_gregorian])
    other_incomes_in_month = other_incomes_base.filter(deposit_date__range=[start_gregorian, end_gregorian])

    subscription_incomes_in_month = Subscription.objects.filter(
        creator=request.user,
        status='success',
        payment_date__range=[start_gregorian, end_gregorian]
    )

    total_subscription_income = subscription_incomes_in_month.aggregate(total=Sum('price'))['total'] or 0
    total_other_income = other_incomes_in_month.aggregate(total=Sum('price'))['total'] or 0
    total_income_monthly = total_subscription_income + total_other_income

    total_expenses_monthly = expenses_in_month.aggregate(total=Sum('price'))['total'] or 0
    net_profit_monthly = total_income_monthly - total_expenses_monthly

    server_costs_monthly = expenses_in_month.filter(is_server_cost=True).aggregate(total=Sum('price'))['total'] or 0
    top_spending_monthly = expenses_in_month.values('issue').annotate(total=Sum('price'),
                                                                      count=Count('issue')).order_by('-total')[:5]

    context = {
        'expense_form': expense_form,
        'other_income_form': other_income_form,
        'years': range(today_jalali.year - 5, today_jalali.year + 2),
        'months': {i: jdatetime.date(1, i, 1).strftime('%B') for i in range(1, 13)},
        'selected_year': selected_year,
        'selected_month': selected_month,
        'total_income_monthly': total_income_monthly,
        'total_expenses_monthly': total_expenses_monthly,
        'net_profit_monthly': net_profit_monthly,
        'server_costs_monthly': server_costs_monthly,
        'incomes_list': other_incomes_in_month.order_by('-deposit_date'),
        'expenses_list': expenses_in_month.order_by('-spending_date'),
        'top_spending_monthly': top_spending_monthly,
    }
    template_name = 'dashboard/desktop/add_transaction.html'
    if getattr(request, 'is_mobile', False):
        template_name = 'dashboard/mobile/add_transaction.html'
    return render(request, template_name, context)


# ===================================================================
# ویوهای مدیریت حساب بانکی
# ===================================================================

@login_required
def bank_account_list_view(request):
    accounts = BankAccount.objects.filter(creator=request.user).order_by('bank_name')
    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.creator = request.user
            account.save()
            messages.success(request, _("Bank account '{name}' created successfully.").format(name=account.bank_name))
            return redirect('dashboard:bank_account_list')
    else:
        form = BankAccountForm()
    return render(request, 'dashboard/desktop/bank_account_list.html', {'form': form, 'accounts': accounts})


@login_required
def bank_account_edit_view(request, pk):
    account = get_object_or_404(BankAccount, id=pk, creator=request.user)
    if request.method == 'POST':
        form = BankAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, _("Bank account '{name}' updated successfully.").format(name=account.bank_name))
            return redirect('dashboard:bank_account_list')
    else:
        form = BankAccountForm(instance=account)
    return render(request, 'dashboard/desktop/bank_account_form.html', {'form': form, 'account': account})


@login_required
@require_POST
def bank_account_delete_view(request, pk):
    account = get_object_or_404(BankAccount, id=pk, creator=request.user)
    account_name = account.bank_name
    account.delete()
    messages.success(request, _("Bank account '{name}' deleted successfully.").format(name=account_name))
    return redirect('dashboard:bank_account_list')


# ===================================================================
# ویوهای اشتراک
# ===================================================================

@login_required
def subscription_dashboard_view(request):
    today = jdatetime.date.today()
    selected_year = request.GET.get('year', str(today.year))
    selected_month = request.GET.get('month', str(today.month))
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')

    if request.method == 'POST':
        if 'add_subscription' in request.POST:
            form = SubscriptionForm(request.POST, user=request.user)
            if form.is_valid():
                subscription = form.save(commit=False)
                subscription.creator = request.user
                subscription.save()
                messages.success(request, _("Subscription for '{customer}' added successfully.").format(
                    customer=subscription.customer.name))
                query_params = f"?year={subscription.year}&month={subscription.month}"
                return redirect(f"{reverse_lazy('dashboard:subscription_dashboard')}{query_params}")
    else:
        form = SubscriptionForm(user=request.user, initial={'year': selected_year, 'month': selected_month})

    subscriptions_query = Subscription.objects.filter(
        creator=request.user,
        year=selected_year,
        month=selected_month
    ).select_related('customer', 'referrer', 'destination_bank').order_by('customer__name')

    if status_filter == 'paid':
        subscriptions_query = subscriptions_query.filter(status='success')
    elif status_filter == 'unpaid':
        subscriptions_query = subscriptions_query.filter(status='pending')

    if search_query:
        subscriptions_query = subscriptions_query.filter(
            Q(customer__name__icontains=search_query) |
            Q(referrer__name__icontains=search_query)
        )

    all_subscriptions_for_month = Subscription.objects.filter(creator=request.user, year=selected_year,
                                                              month=selected_month)
    total_giga = subscriptions_query.aggregate(total=Sum('giga'))['total'] or 0
    paid_amount = all_subscriptions_for_month.filter(status='success').aggregate(total=Sum('price'))['total'] or 0
    unpaid_amount = all_subscriptions_for_month.filter(status='pending').aggregate(total=Sum('price'))['total'] or 0
    total_amount = paid_amount + unpaid_amount

    context = {
        'form': form,
        'subscriptions': subscriptions_query,
        'total_giga_sold': total_giga,
        'paid_amount': paid_amount,
        'unpaid_amount': unpaid_amount,
        'total_amount': total_amount,
        'years': range(today.year - 5, today.year + 2),
        'months': {i: jdatetime.date(1, i, 1).strftime('%B') for i in range(1, 13)},
        'selected_year': int(selected_year),
        'selected_month': int(selected_month),
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'dashboard/desktop/subscription_dashboard.html', context)


@login_required
def subscription_edit_view(request, pk):
    subscription = get_object_or_404(Subscription, id=pk, creator=request.user)
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=subscription, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Subscription for '{customer}' updated successfully.").format(
                customer=subscription.customer.name))
            return redirect(
                f"{reverse_lazy('dashboard:subscription_dashboard')}?year={subscription.year}&month={subscription.month}")
    else:
        form = SubscriptionForm(instance=subscription, user=request.user)

    return render(request, 'dashboard/desktop/subscription_form.html', {'form': form, 'subscription': subscription})


@login_required
@require_POST
def subscription_delete_view(request, pk):
    subscription = get_object_or_404(Subscription, id=pk, creator=request.user)
    customer_name = subscription.customer.name
    year, month = subscription.year, subscription.month
    subscription.delete()
    messages.success(request, _("Subscription for '{name}' deleted successfully.").format(name=customer_name))
    return redirect(f"{reverse_lazy('dashboard:subscription_dashboard')}?year={year}&month={month}")


# ===================================================================
# ویوهای مشتریان
# ===================================================================

@login_required
def customer_profile_list_view(request):
    customers = CustomerProfile.objects.filter(creator=request.user).order_by('name')
    customer_count = customers.count()

    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, user=request.user)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.creator = request.user
            customer.save()
            messages.success(request, _("Customer '{name}' created successfully.").format(name=customer.name))
            return redirect('dashboard:customer_profile_list')
    else:
        form = CustomerProfileForm(user=request.user)

    return render(request, 'dashboard/desktop/customer_profile_list.html', {
        'form': form,
        'customers': customers,
        'customer_count': customer_count
    })


@login_required
def edit_customer_profile(request, pk):
    customer = get_object_or_404(CustomerProfile, id=pk, creator=request.user)
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=customer, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Customer '{name}' updated successfully.").format(name=customer.name))
            return redirect('dashboard:customer_profile_list')
    else:
        form = CustomerProfileForm(instance=customer, user=request.user)

    return render(request, 'dashboard/desktop/edit_customer_profile.html', {'form': form, 'customer': customer})


# ===================================================================
# ویو گزارش مالی
# ===================================================================
@login_required
def financial_report_view(request):
    today_jalali = jdatetime.date.today()
    selected_year = request.GET.get('year', str(today_jalali.year))
    selected_month = request.GET.get('month')

    expenses_base = Expense.objects.filter(creator=request.user)
    other_incomes_base = OtherIncome.objects.filter(creator=request.user)
    subscriptions_base = Subscription.objects.filter(creator=request.user, status='success')

    expenses_stats = expenses_base
    other_incomes_stats = other_incomes_base
    subscription_incomes_stats = subscriptions_base

    if selected_year and selected_year.isdigit():
        year = int(selected_year)
        start_date_jalali = jdatetime.date(year, 1, 1)
        end_date_jalali = jdatetime.date(year, 12, 29)
        if jdatetime.date(year, 1, 1).isleap():
            end_date_jalali = jdatetime.date(year, 12, 30)

        start_gregorian = start_date_jalali.togregorian()
        end_gregorian = end_date_jalali.togregorian()

        if selected_month and selected_month.isdigit():
            month = int(selected_month)
            start_date_jalali = jdatetime.date(year, month, 1)
            days_in_month = 31 if month < 7 else (30 if month < 12 else (30 if start_date_jalali.isleap() else 29))
            end_date_jalali = jdatetime.date(year, month, days_in_month)
            start_gregorian = start_date_jalali.togregorian()
            end_gregorian = end_date_jalali.togregorian()

        expenses_stats = expenses_stats.filter(spending_date__range=[start_gregorian, end_gregorian])
        other_incomes_stats = other_incomes_stats.filter(deposit_date__range=[start_gregorian, end_gregorian])
        subscription_incomes_stats = subscription_incomes_stats.filter(
            payment_date__range=[start_gregorian, end_gregorian])

    total_subscription_income = subscription_incomes_stats.aggregate(total=Sum('price'))['total'] or 0
    total_other_income = other_incomes_stats.aggregate(total=Sum('price'))['total'] or 0
    total_income = total_subscription_income + total_other_income
    total_expenses = expenses_stats.aggregate(total=Sum('price'))['total'] or 0
    net_profit = total_income - total_expenses

    today_gregorian = timezone.now().date()
    total_today_income = (Subscription.objects.filter(creator=request.user, status='success',
                                                      payment_date=today_gregorian).aggregate(s=Sum('price'))[
                              's'] or 0) + \
                         (OtherIncome.objects.filter(creator=request.user, deposit_date=today_gregorian).aggregate(
                             s=Sum('price'))['s'] or 0)
    total_today_expenses = \
        Expense.objects.filter(creator=request.user, spending_date=today_gregorian).aggregate(s=Sum('price'))['s'] or 0

    timeframe = request.GET.get('timeframe', 'monthly')
    chart_labels, income_data, expense_data = [], [], []

    chart_year = int(selected_year)
    if not selected_month:
        timeframe = 'monthly'

    if timeframe == 'daily' and selected_month and selected_month.isdigit():
        chart_month = int(selected_month)
        start_date = jdatetime.date(chart_year, chart_month, 1)
        days_in_month = 31 if chart_month < 7 else 30
        if chart_month == 12: days_in_month = 29 if not start_date.isleap() else 30

        chart_labels = [d.strftime('%d') for d in [start_date + timedelta(days=i) for i in range(days_in_month)]]

        month_start_g = start_date.togregorian()
        month_end_g = (start_date + timedelta(days=days_in_month - 1)).togregorian()

        income_q = subscriptions_base.filter(payment_date__range=[month_start_g, month_end_g])
        other_income_q = other_incomes_base.filter(deposit_date__range=[month_start_g, month_end_g])
        expense_q = expenses_base.filter(spending_date__range=[month_start_g, month_end_g])

        for day in range(1, days_in_month + 1):
            gregorian_day = jdatetime.date(chart_year, chart_month, day).togregorian()
            daily_income = (income_q.filter(payment_date=gregorian_day).aggregate(s=Sum('price'))['s'] or 0) + \
                           (other_income_q.filter(deposit_date=gregorian_day).aggregate(s=Sum('price'))['s'] or 0)
            daily_expense = expense_q.filter(spending_date=gregorian_day).aggregate(s=Sum('price'))['s'] or 0
            income_data.append(int(daily_income))
            expense_data.append(int(daily_expense))
    else:
        timeframe = 'monthly'
        chart_labels = [jdatetime.date(1, i, 1).strftime('%B') for i in range(1, 13)]

        year_start_g = jdatetime.date(chart_year, 1, 1).togregorian()
        year_end_g = (
                jdatetime.date(chart_year, 12, 1) + timedelta(days=30)).togregorian()

        income_by_month = {i: 0 for i in range(1, 13)}
        expense_by_month = {i: 0 for i in range(1, 13)}

        all_incomes = subscriptions_base.filter(payment_date__year=year_start_g.year).annotate(
            month_g=TruncMonth('payment_date')).values('month_g').annotate(total=Sum('price'))
        all_other_incomes = other_incomes_base.filter(deposit_date__year=year_start_g.year).annotate(
            month_g=TruncMonth('deposit_date')).values('month_g').annotate(total=Sum('price'))
        all_expenses = expenses_base.filter(spending_date__year=year_start_g.year).annotate(
            month_g=TruncMonth('spending_date')).values('month_g').annotate(total=Sum('price'))

        for inc in all_incomes: income_by_month[inc['month_g'].month] += inc['total']
        for inc in all_other_incomes: income_by_month[inc['month_g'].month] += inc['total']
        for exp in all_expenses: expense_by_month[exp['month_g'].month] += exp['total']

        income_data = [int(income_by_month.get(i, 0)) for i in range(1, 13)]
        expense_data = [int(expense_by_month.get(i, 0)) for i in range(1, 13)]

    recent_expenses = Expense.objects.filter(creator=request.user).order_by('-created_at')[:5]
    recent_incomes = OtherIncome.objects.filter(creator=request.user).order_by('-created_at')[:5]
    recent_customers = CustomerProfile.objects.filter(creator=request.user).order_by('-created_at')[:5]
    recent_subscriptions = Subscription.objects.filter(creator=request.user, status='success').order_by(
        '-payment_date')[:5]

    recent_activities = sorted(
        chain(recent_expenses, recent_incomes, recent_customers, recent_subscriptions),
        key=lambda instance: getattr(instance, 'created_at', None) or getattr(instance, 'payment_date', None),
        reverse=True
    )[:7]

    top_expenses = expenses_stats.values('issue').annotate(total=Sum('price'), count=Count('issue')).order_by('-total')[
        :10]

    context = {
        'expenses': expenses_stats.order_by('-spending_date'),
        'other_incomes': other_incomes_stats.order_by('-deposit_date'),
        'years': range(today_jalali.year - 5, today_jalali.year + 2),
        'months': {i: jdatetime.date(1, i, 1).strftime('%B') for i in range(1, 13)},
        'selected_year': selected_year,
        'selected_month': selected_month,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'total_today_income': total_today_income,
        'total_today_expenses': total_today_expenses,
        'chart_labels': chart_labels,
        'income_data': income_data,
        'expense_data': expense_data,
        'recent_activities': recent_activities,
        'current_timeframe': timeframe,
        'top_expenses': top_expenses,
    }
    return render(request, 'dashboard/desktop/financial_report.html', context)


# ===================================================================
# سایر ویوها
# ===================================================================

@login_required
@require_POST
def delete_customer_profile(request, pk):
    customer = get_object_or_404(CustomerProfile, id=pk, creator=request.user)
    customer_name = customer.name
    customer.delete()
    messages.success(request, _("Customer '{name}' and all their subscriptions deleted successfully.").format(
        name=customer_name))
    return redirect('dashboard:customer_profile_list')


@login_required
def profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, instance=request.user)
        password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if 'change_details' in request.POST and user_form.is_valid():
            user_form.save()
            messages.success(request, _('Profile details updated successfully.'))
            return redirect('dashboard:profile')
        if 'change_password' in request.POST and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, _('Password changed successfully.'))
            return redirect('dashboard:profile')
        if 'change_avatar' in request.POST and profile_form.is_valid():
            profile_form.save()
            messages.success(request, _('Your avatar was successfully updated!'))
            return redirect('dashboard:profile')
    else:
        user_form = UserProfileForm(instance=request.user)
        password_form = CustomPasswordChangeForm(user=request.user)
        profile_form = ProfileUpdateForm(instance=profile)
    context = {'user_form': user_form, 'password_form': password_form, 'profile_form': profile_form}
    return render(request, 'dashboard/desktop/profile.html', context)


@login_required
@require_POST
def set_theme_view(request):
    theme = request.POST.get('theme')
    if theme in ['light', 'dark']:
        profile, created = Profile.objects.get_or_create(user=request.user)
        profile.theme = theme
        profile.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)


def _get_transaction_redirect_url(request):
    redirect_url = reverse('dashboard:add_transaction')
    year = request.POST.get('year', request.GET.get('year'))
    month = request.POST.get('month', request.GET.get('month'))
    if year and month:
        redirect_url += f"?year={year}&month={month}"
    elif 'next' in request.POST or 'next' in request.GET:
        redirect_url = request.POST.get('next', request.GET.get('next'))
    return redirect_url


@login_required
@require_POST
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, id=pk, creator=request.user)
    expense.delete()
    messages.success(request, _("Expense deleted successfully."))
    if request.POST.get('year') and request.POST.get('month'):
        return redirect(_get_transaction_redirect_url(request))
    return redirect('dashboard:financial_report')


@login_required
@require_POST
def delete_other_income(request, pk):
    income = get_object_or_404(OtherIncome, id=pk, creator=request.user)
    income.delete()
    messages.success(request, _("Income deleted successfully."))
    if request.POST.get('year') and request.POST.get('month'):
        return redirect(_get_transaction_redirect_url(request))
    return redirect('dashboard:financial_report')


@login_required
def expense_edit_view(request, pk):
    expense = get_object_or_404(Expense, id=pk, creator=request.user)
    redirect_url = _get_transaction_redirect_url(request)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, _("Expense updated successfully."))
            return redirect(redirect_url)
    else:
        form = ExpenseForm(instance=expense)
    return render(request, 'dashboard/desktop/expense_edit_form.html', {
        'form': form,
        'expense': expense,
        'redirect_url': redirect_url
    })


@login_required
def other_income_edit_view(request, pk):
    income = get_object_or_404(OtherIncome, id=pk, creator=request.user)
    redirect_url = _get_transaction_redirect_url(request)
    if request.method == 'POST':
        form = OtherIncomeForm(request.POST, instance=income)
        if form.is_valid():
            form.save()
            messages.success(request, _("Income updated successfully."))
            return redirect(redirect_url)
    else:
        form = OtherIncomeForm(instance=income)
    return render(request, 'dashboard/desktop/other_income_edit_form.html', {
        'form': form,
        'income': income,
        'redirect_url': redirect_url
    })


def custom_404(request, exception):
    return render(request, '404.html', {}, status=404)


def custom_403(request, exception):
    return render(request, '403.html', {}, status=403)


@login_required
def get_customer_details(request):
    customer_id = request.GET.get('customer_id')
    if customer_id:
        try:
            customer = CustomerProfile.objects.get(id=customer_id)
            referrer_id = customer.referred_by.id if customer.referred_by else None
            return JsonResponse({'referrer_id': referrer_id})
        except CustomerProfile.DoesNotExist:
            return JsonResponse({'error': 'Customer not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'No ID provided'}, status=400)


# ===================================================================
# SYSTEM BACKUP VIEWS (Secure)
# ===================================================================

@login_required
@user_passes_test(lambda u: u.is_superuser)
def backup_panel(request):
    """نمایش صفحه مدیریت بک‌آپ - فقط برای ادمین کل"""
    return render(request, 'dashboard/desktop/backup_panel.html')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def download_backup(request):
    """دانلود مستقیم فایل SQL"""
    filename = f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql"

    # ✅ نکته مهم: دقیقاً همان دستوری که در تلگرام کار کرد (با --skip-ssl)
    command = f"mysqldump --skip-ssl -h {DB_HOST} -u {DB_USER} -p'{DB_PASSWORD}' --no-tablespaces {DB_NAME}"

    try:
        # اجرای دستور
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()

        if process.returncode != 0:
            # اگر خطایی بود، متن خطا را برگردان
            return HttpResponse(f"Error creating backup: {error.decode('utf-8')}", status=500)

        # اگر موفق بود، فایل را برای دانلود بفرست
        response = HttpResponse(output, content_type='application/sql')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        return HttpResponse(f"System Error: {str(e)}", status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def telegram_backup(request):
    """روش تضمینی: ساخت فایل در پایتون بدون وابستگی به شل پیچیده"""

    # نام فایل‌ها
    raw_filename = f"/tmp/{DB_NAME}_raw.sql"
    zip_filename = f"/tmp/{DB_NAME}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql.gz"

    # دستور mysqldump (ساده و بدون gzip در دستور)
    command = f"mysqldump --skip-ssl -h {DB_HOST} -u {DB_USER} -p'{DB_PASSWORD}' --no-tablespaces {DB_NAME}"

    try:
        # 1. اجرای mysqldump و ذخیره در فایل خام
        with open(raw_filename, 'w') as f:
            process = subprocess.Popen(command, shell=True, stdout=f, stderr=subprocess.PIPE)
            _, error = process.communicate()

        if process.returncode != 0:
            return JsonResponse({'status': 'error', 'message': f"Dump Error: {error.decode('utf-8')}"})

        # 2. بررسی اینکه فایل خام خالی نباشد
        if os.path.getsize(raw_filename) == 0:
            return JsonResponse({'status': 'error', 'message': "Generated SQL file is empty!"})

        # 3. فشرده‌سازی فایل با پایتون (Gzip)
        with open(raw_filename, 'rb') as f_in:
            with gzip.open(zip_filename, 'wb') as f_out:
                f_out.writelines(f_in)

        # 4. ارسال به تلگرام
        caption = f"✅ Backup Successful (Python)\n📅 Date: {datetime.now()}\n🗄 DB: {DB_NAME}"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

        with open(zip_filename, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': CHAT_ID, 'caption': caption}
            response = requests.post(url, files=files, data=data)

        # 5. پاکسازی فایل‌های موقت
        if os.path.exists(raw_filename): os.remove(raw_filename)
        if os.path.exists(zip_filename): os.remove(zip_filename)

        telegram_resp = response.json()
        if response.status_code == 200 and telegram_resp.get('ok'):
            return JsonResponse({'status': 'success', 'message': 'Backup sent successfully!'})
        else:
            return JsonResponse({'status': 'error', 'message': f"Telegram Error: {telegram_resp}"})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def restore_db(request):
    """بازگردانی دیتابیس (خطرناک)"""
    if request.method == 'POST' and request.FILES.get('sql_file'):
        sql_file = request.FILES['sql_file']
        temp_path = f"/tmp/restore_{sql_file.name}"

        with open(temp_path, 'wb+') as destination:
            for chunk in sql_file.chunks():
                destination.write(chunk)

        if temp_path.endswith('.gz'):
            cmd = f"gunzip < {temp_path} | mysql -h {DB_HOST} -u {DB_USER} -p'{DB_PASSWORD}' {DB_NAME}"
        else:
            cmd = f"mysql -h {DB_HOST} -u {DB_USER} -p'{DB_PASSWORD}' {DB_NAME} < {temp_path}"

        try:
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if os.path.exists(temp_path):
                os.remove(temp_path)

            if process.returncode == 0:
                messages.success(request, "Database restored successfully!")
            else:
                messages.error(request, f"Restore Failed: {process.stderr}")
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")

        return redirect('dashboard:backup_panel')

    return redirect('dashboard:backup_panel')


@login_required
def main_dashboard_view(request):
    """
    Main Dashboard: Shows daily statistics and PAGINATED recent activities.
    Supports Mobile/Desktop views via redirection.
    """

    if is_mobile(request):
        return redirect('dashboard:mobile_home')

    # --- از اینجا به بعد فقط مخصوص دسکتاپ است ---
    today = timezone.now().date()

    # 1. Daily Stats
    subs_today = Subscription.objects.filter(creator=request.user, status='success', payment_date=today)
    subs_income_today = subs_today.aggregate(total=Sum('price'))['total'] or 0
    subs_count_today = subs_today.count()

    other_income_today = \
    OtherIncome.objects.filter(creator=request.user, deposit_date=today).aggregate(total=Sum('price'))['total'] or 0
    expenses_today = Expense.objects.filter(creator=request.user, spending_date=today).aggregate(total=Sum('price'))[
                         'total'] or 0

    total_income_today = subs_income_today + other_income_today
    net_profit_today = total_income_today - expenses_today

    # 2. Recent Activity (Desktop needs Pagination)
    all_expenses = Expense.objects.filter(creator=request.user).order_by('-created_at')
    all_incomes = OtherIncome.objects.filter(creator=request.user).order_by('-created_at')
    all_subscriptions = Subscription.objects.filter(creator=request.user, status='success').order_by('-payment_date')

    full_activity_list = sorted(
        chain(all_expenses, all_incomes, all_subscriptions),
        key=lambda instance: getattr(instance, 'created_at', None) or getattr(instance, 'payment_date', None),
        reverse=True
    )

    paginator = Paginator(full_activity_list, 20)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'total_income_today': total_income_today,
        'expenses_today': expenses_today,
        'net_profit_today': net_profit_today,
        'subs_count_today': subs_count_today,
        'page_obj': page_obj,
    }

    return render(request, 'dashboard/desktop/main_dashboard.html', context)


@login_required
def bank_report_view(request):
    # دریافت تاریخ امروز برای تنظیم پیش‌فرض‌ها
    current_date = jdatetime.date.today()
    selected_year = request.GET.get('year', str(current_date.year))
    selected_month = request.GET.get('month', str(current_date.month))

    try:
        year_num = int(selected_year)
        month_num = int(selected_month)
    except ValueError:
        year_num = current_date.year
        month_num = current_date.month

    # محاسبه تاریخ شروع و پایان برای فیلتر کردن
    try:
        start_date = jdatetime.date(year_num, month_num, 1).togregorian()
        if month_num == 12:
            end_date = jdatetime.date(year_num + 1, 1, 1).togregorian()
        else:
            end_date = jdatetime.date(year_num, month_num + 1, 1).togregorian()
    except Exception:
        start_date = current_date.togregorian()
        end_date = current_date.togregorian()

    # --- شروع پردازش بانک‌ها ---
    banks = BankAccount.objects.filter(creator=request.user)
    bank_stats = []
    total_assets = 0

    for bank in banks:
        # A. محاسبه اشتراک‌ها
        subs_qs = Subscription.objects.filter(
            creator=request.user,
            destination_bank=bank,
            status='success',
            year=year_num,
            month=month_num
        )
        subs_income = subs_qs.aggregate(total=Sum('price'))['total'] or 0

        # B. محاسبه سایر درآمدها
        other_qs = OtherIncome.objects.filter(
            creator=request.user,
            destination_bank=bank,
            deposit_date__gte=start_date,
            deposit_date__lt=end_date
        )
        other_income = other_qs.aggregate(total=Sum('price'))['total'] or 0

        # C. محاسبه هزینه‌ها
        expense_qs = Expense.objects.filter(
            creator=request.user,
            source_bank=bank,
            spending_date__gte=start_date,
            spending_date__lt=end_date
        )
        total_expense = expense_qs.aggregate(total=Sum('price'))['total'] or 0

        # D. محاسبه موجودی خالص
        net_balance = (subs_income + other_income) - total_expense
        total_assets += net_balance

        bank_stats.append({
            'bank': bank,
            'subs_income': subs_income,
            'other_income': other_income,
            'total_expense': total_expense,
            'net_balance': net_balance
        })

    # --- تنظیمات هوشمند تقویم ---

    # 1. سال‌ها: از ۳ سال پیش تا ۱ سال بعد (به صورت خودکار آپدیت می‌شود)
    current_year_num = current_date.year
    years = range(current_year_num - 3, current_year_num + 2)

    # 2. ماه‌ها: به صورت فینگلیش (طبق درخواست شما)
    months = {
        1: 'Farvardin', 2: 'Ordibehesht', 3: 'Khordad', 4: 'Tir', 5: 'Mordad', 6: 'Shahrivar',
        7: 'Mehr', 8: 'Aban', 9: 'Azar', 10: 'Dey', 11: 'Bahman', 12: 'Esfand'
    }

    context = {
        'bank_stats': bank_stats,
        'total_assets': total_assets,
        'selected_year': int(selected_year),
        'selected_month': int(selected_month),
        'years': years,
        'months': months,
    }
    return render(request, 'dashboard/desktop/bank_report.html', context)