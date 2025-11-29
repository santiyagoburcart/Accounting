# Accounting/dashboard/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils.translation import gettext as _
from django.urls import reverse_lazy, reverse
from .forms import (
    UserProfileForm, CustomPasswordChangeForm, ExpenseForm,
    OtherIncomeForm, ProfileUpdateForm, SubscriptionForm, CustomerProfileForm,
    BankAccountForm,CustomAuthenticationForm
)
from .models import (
    Expense, OtherIncome, Profile, Subscription, CustomerProfile,
    BankAccount
)
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from itertools import chain
from operator import attrgetter
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
import jdatetime
import pandas as pd
from django.views.decorators.http import require_POST

from django.template.defaulttags import register


@register.filter
def class_name(value):
    return value.__class__.__name__


class CustomLoginView(LoginView):
    template_name = 'dashboard/login.html'
    redirect_authenticated_user = True
    authentication_form = CustomAuthenticationForm # <-- ۲. به ویو بگویید ا


# ===================================================================
# START: ویو جدید برای صفحه افزودن تراکنش (بر اساس معماری جدید)
# ===================================================================
@login_required
def add_transaction_view(request):
    """
    داشبورد مدیریت تراکنش‌ها: شامل فرم‌های ورود اطلاعات و نمایش آمار ماهانه.
    """
    # --- بخش پردازش فرم‌ها (POST requests) ---
    expense_form = ExpenseForm(prefix='expense')
    other_income_form = OtherIncomeForm(prefix='income')

    # برای اینکه بعد از افزودن تراکنش به همان ماه فیلتر شده بازگردیم
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

    # --- بخش فیلتر و نمایش آمار (GET requests) ---
    today_jalali = jdatetime.date.today()
    selected_year = request.GET.get('year', str(today_jalali.year))
    selected_month = request.GET.get('month', str(today_jalali.month))

    # کوئری‌های پایه
    expenses_base = Expense.objects.filter(creator=request.user)
    other_incomes_base = OtherIncome.objects.filter(creator=request.user)

    # محاسبه محدوده تاریخ میلادی برای ماه و سال شمسی انتخاب شده
    year, month = int(selected_year), int(selected_month)
    start_date_jalali = jdatetime.date(year, month, 1)
    days_in_month = 31 if month < 7 else (30 if month < 12 else (30 if start_date_jalali.isleap() else 29))
    end_date_jalali = jdatetime.date(year, month, days_in_month)
    start_gregorian = start_date_jalali.togregorian()
    end_gregorian = end_date_jalali.togregorian()

    # فیلتر کردن داده‌ها بر اساس محدوده تاریخ
    expenses_in_month = expenses_base.filter(spending_date__range=[start_gregorian, end_gregorian])
    other_incomes_in_month = other_incomes_base.filter(deposit_date__range=[start_gregorian, end_gregorian])

    # درآمد اشتراک‌ها برای ماه مربوطه باید جداگانه محاسبه شود
    subscription_incomes_in_month = Subscription.objects.filter(
        creator=request.user,
        status='success',
        payment_date__range=[start_gregorian, end_gregorian]
    )

    # --- محاسبه آمار ماهانه ---
    total_subscription_income = subscription_incomes_in_month.aggregate(total=Sum('price'))['total'] or 0
    total_other_income = other_incomes_in_month.aggregate(total=Sum('price'))['total'] or 0
    total_income_monthly = total_subscription_income + total_other_income

    total_expenses_monthly = expenses_in_month.aggregate(total=Sum('price'))['total'] or 0
    net_profit_monthly = total_income_monthly - total_expenses_monthly

    # محاسبه هزینه سرور و دسته‌بندی هزینه‌ها
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

        # آمار ماهانه
        'total_income_monthly': total_income_monthly,
        'total_expenses_monthly': total_expenses_monthly,
        'net_profit_monthly': net_profit_monthly,
        'server_costs_monthly': server_costs_monthly,

        # لیست‌های ماهانه
        'incomes_list': other_incomes_in_month.order_by('-deposit_date'),
        'expenses_list': expenses_in_month.order_by('-spending_date'),
        'top_spending_monthly': top_spending_monthly,
    }
    return render(request, 'dashboard/add_transaction.html', context)


# END: CHANGE


# ===================================================================
# ویوهای مدیریت حساب بانکی (کد شما - بدون تغییر)
# ===================================================================

@login_required
def bank_account_list_view(request):
    """ویو برای نمایش لیست حساب‌های بانکی و افزودن حساب جدید"""
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
    return render(request, 'dashboard/bank_account_list.html', {'form': form, 'accounts': accounts})


@login_required
def bank_account_edit_view(request, pk):
    """ویو برای ویرایش حساب بانکی"""
    account = get_object_or_404(BankAccount, id=pk, creator=request.user)
    if request.method == 'POST':
        form = BankAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, _("Bank account '{name}' updated successfully.").format(name=account.bank_name))
            return redirect('dashboard:bank_account_list')
    else:
        form = BankAccountForm(instance=account)
    return render(request, 'dashboard/bank_account_form.html', {'form': form, 'account': account})


@login_required
@require_POST
def bank_account_delete_view(request, pk):
    """ویو برای حذف حساب بانکی"""
    account = get_object_or_404(BankAccount, id=pk, creator=request.user)
    account_name = account.bank_name
    account.delete()
    messages.success(request, _("Bank account '{name}' deleted successfully.").format(name=account_name))
    return redirect('dashboard:bank_account_list')


# ===================================================================
# ویوهای اشتراک (تغییر در بخش جستجو)
# ===================================================================

@login_required
def subscription_dashboard_view(request):
    """
    داشبورد اصلی برای نمایش و مدیریت سرویس‌های ماهانه
    """
    today = jdatetime.date.today()
    selected_year = request.GET.get('year', str(today.year))
    selected_month = request.GET.get('month', str(today.month))
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')

    # *** START: CHANGE ***
    # فرم افزودن اشتراک اکنون در مودال است، اما منطق POST دقیقاً
    # مانند قبل در همین ویو انجام می‌شود.
    if request.method == 'POST':
        if 'add_subscription' in request.POST:
            form = SubscriptionForm(request.POST, user=request.user)
            if form.is_valid():
                subscription = form.save(commit=False)
                subscription.creator = request.user
                subscription.save()
                messages.success(request, _("Subscription for '{customer}' added successfully.").format(
                    customer=subscription.customer.name))
                # بازگشت به همان صفحه با همان فیلترها
                query_params = f"?year={subscription.year}&month={subscription.month}"
                return redirect(f"{reverse_lazy('dashboard:subscription_dashboard')}{query_params}")
            # اگر فرم معتبر نباشد، ویو به صورت خودکار فرم را
            # همراه با خطاها به تمپلیت ارسال می‌کند.
    else:
        form = SubscriptionForm(user=request.user, initial={'year': selected_year, 'month': selected_month})
    # *** END: CHANGE ***

    subscriptions_query = Subscription.objects.filter(
        creator=request.user,
        year=selected_year,
        month=selected_month
    ).select_related('customer', 'referrer', 'destination_bank').order_by('customer__name')

    if status_filter == 'paid':
        subscriptions_query = subscriptions_query.filter(status='success')
    elif status_filter == 'unpaid':
        subscriptions_query = subscriptions_query.filter(status='pending')

    # *** START: CHANGE ***
    # منطق جستجو برای پشتیبانی از مشتری و معرف (Referrer)
    if search_query:
        subscriptions_query = subscriptions_query.filter(
            Q(customer__name__icontains=search_query) |
            Q(referrer__name__icontains=search_query)
        )
    # *** END: CHANGE ***

    all_subscriptions_for_month = Subscription.objects.filter(creator=request.user, year=selected_year,
                                                              month=selected_month)
    total_giga = subscriptions_query.aggregate(total=Sum('giga'))['total'] or 0
    paid_amount = all_subscriptions_for_month.filter(status='success').aggregate(total=Sum('price'))['total'] or 0
    unpaid_amount = all_subscriptions_for_month.filter(status='pending').aggregate(total=Sum('price'))['total'] or 0
    total_amount = paid_amount + unpaid_amount

    context = {
        'form': form, # فرم باید همیشه به تمپلیت ارسال شود (برای مودال)
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
    return render(request, 'dashboard/subscription_dashboard.html', context)


@login_required
def subscription_edit_view(request, pk):
    """ویو برای ویرایش یک اشتراک"""
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

    return render(request, 'dashboard/subscription_form.html', {'form': form, 'subscription': subscription})


@login_required
@require_POST
def subscription_delete_view(request, pk):
    """ویو برای حذف یک اشتراک"""
    subscription = get_object_or_404(Subscription, id=pk, creator=request.user)
    customer_name = subscription.customer.name
    year, month = subscription.year, subscription.month
    subscription.delete()
    messages.success(request, _("Subscription for '{name}' deleted successfully.").format(name=customer_name))
    return redirect(f"{reverse_lazy('dashboard:subscription_dashboard')}?year={year}&month={month}")


# ===================================================================
# ویوهای مشتریان (کد شما - بدون تغییر)
# ===================================================================

@login_required
def customer_profile_list_view(request):
    """
    ویو جدید برای نمایش لیست مشتریان و افزودن مشتری جدید
    """
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

    return render(request, 'dashboard/customer_profile_list.html', {
        'form': form,
        'customers': customers,
        'customer_count': customer_count
    })


@login_required
def edit_customer_profile(request, pk):
    """
    ویو جدید برای ویرایش پروفایل مشتری
    """
    customer = get_object_or_404(CustomerProfile, id=pk, creator=request.user)
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=customer, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Customer '{name}' updated successfully.").format(name=customer.name))
            return redirect('dashboard:customer_profile_list')
    else:
        form = CustomerProfileForm(instance=customer, user=request.user)

    return render(request, 'dashboard/edit_customer_profile.html', {'form': form, 'customer': customer})


# ===================================================================
# START: CHANGE - ویو گزارش مالی ساده‌سازی شد (فقط نمایش)
# ===================================================================
@login_required
def financial_report_view(request):
    """
    گزارش مالی بهبودیافته (فقط برای نمایش داده‌ها).
    """
    # **تغییر**: منطق پردازش فرم‌ها از اینجا حذف شده است.

    # ------------------- منطق فیلتر و آمار (کد شما - بدون تغییر) -------------------
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

    # ------------------- منطق نمودار (چارت) (کد شما - با بهبود جزئی) -------------------
    timeframe = request.GET.get('timeframe', 'monthly')
    chart_labels, income_data, expense_data = [], [], []

    chart_year = int(selected_year)
    # اگر ماه انتخاب نشده باشد، نمایش نمودار همیشه باید "ماهانه" باشد
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
        timeframe = 'monthly'  # اطمینان از اینکه تایم‌فریم ماهانه است
        chart_labels = [jdatetime.date(1, i, 1).strftime('%B') for i in range(1, 13)]

        year_start_g = jdatetime.date(chart_year, 1, 1).togregorian()
        year_end_g = (
                    jdatetime.date(chart_year, 12, 1) + timedelta(days=30)).togregorian()  # راه ساده‌تر برای پایان سال

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

    # ------------------- منطق فعالیت‌های اخیر (کد شما - بدون تغییر) -------------------
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
        # **تغییر**: فرم‌ها از کانتکست این ویو حذف شدند
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
    return render(request, 'dashboard/financial_report.html', context)


# ===================================================================
# سایر ویوها (کد شما - بدون تغییر)
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
    return render(request, 'dashboard/profile.html', context)


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
    """
    یک هلپر برای ساخت URL بازگشت به صفحه تراکنش‌ها
    همراه با حفظ فیلترهای ماه و سال.
    """
    redirect_url = reverse('dashboard:add_transaction')

    # اولویت با پارامترهای GET یا POST است
    year = request.POST.get('year', request.GET.get('year'))
    month = request.POST.get('month', request.GET.get('month'))

    if year and month:
        redirect_url += f"?year={year}&month={month}"

    # اگر هیچکدام نبود، سعی کن از 'next' استفاده کنی
    elif 'next' in request.POST or 'next' in request.GET:
        redirect_url = request.POST.get('next', request.GET.get('next'))
        # اگر 'next' پارامترهای فیلتر را داشت، همان را برمی‌گرداند

    return redirect_url


@login_required
@require_POST
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, id=pk, creator=request.user)
    expense.delete()
    messages.success(request, _("Expense deleted successfully."))
    #return redirect('dashboard:financial_report')

    # اول چک می‌کنیم آیا درخواست از صفحه add_transaction آمده (با فیلتر)
    if request.POST.get('year') and request.POST.get('month'):
        return redirect(_get_transaction_redirect_url(request))

    # اگر نه، به رفتار قبلی (صفحه ریپورت) بازمی‌گردد
    return redirect('dashboard:financial_report')


@login_required
@require_POST
def delete_other_income(request, pk):
    income = get_object_or_404(OtherIncome, id=pk, creator=request.user)
    income.delete()
    messages.success(request, _("Income deleted successfully."))
    #return redirect('dashboard:financial_report')

    # **تغییر اصلی**: به جای ریدایرکت ثابت، از هلپر استفاده می‌کنیم
    # return redirect('dashboard:financial_report') # <-- این خط حذف می‌شود

    # اول چک می‌کنیم آیا درخواست از صفحه add_transaction آمده (با فیلتر)
    if request.POST.get('year') and request.POST.get('month'):
        return redirect(_get_transaction_redirect_url(request))

    # اگر نه، به رفتار قبلی (صفحه ریپورت) بازمی‌گردد
    return redirect('dashboard:financial_report')




@login_required
def expense_edit_view(request, pk):
    """ویو برای ویرایش یک هزینه"""
    expense = get_object_or_404(Expense, id=pk, creator=request.user)
    # URL بازگشت را با فیلترها می‌سازیم
    redirect_url = _get_transaction_redirect_url(request)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, _("Expense updated successfully."))
            return redirect(redirect_url)
    else:
        form = ExpenseForm(instance=expense)

    return render(request, 'dashboard/expense_edit_form.html', {
        'form': form,
        'expense': expense,
        'redirect_url': redirect_url # برای دکمه "انصراف"
    })

@login_required
def other_income_edit_view(request, pk):
    """ویو برای ویرایش یک درآمد (سایر)"""
    income = get_object_or_404(OtherIncome, id=pk, creator=request.user)
    # URL بازگشت را با فیلترها می‌سازیم
    redirect_url = _get_transaction_redirect_url(request)

    if request.method == 'POST':
        form = OtherIncomeForm(request.POST, instance=income)
        if form.is_valid():
            form.save()
            messages.success(request, _("Income updated successfully."))
            return redirect(redirect_url)
    else:
        form = OtherIncomeForm(instance=income)

    return render(request, 'dashboard/other_income_edit_form.html', {
        'form': form,
        'income': income,
        'redirect_url': redirect_url # برای دکمه "انصراف"
    })


def custom_404(request, exception):
    return render(request, '404.html', {}, status=404)


def custom_403(request, exception):
    return render(request, '403.html', {}, status=403)