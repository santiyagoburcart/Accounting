from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils.translation import gettext as _
from .forms import (
    CustomerForm, UserProfileForm, CustomPasswordChangeForm,
    ExpenseForm, OtherIncomeForm, ProfileUpdateForm
)
from .models import Customer, Expense, OtherIncome, Profile
from django.db.models import Sum, Count
from django.utils import timezone
from itertools import chain
from operator import attrgetter
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
import jdatetime
import pandas as pd


# A custom template filter to get class name
from django.template.defaulttags import register


@register.filter
def class_name(value):
    return value.__class__.__name__


class CustomLoginView(LoginView):
    template_name = 'dashboard/login.html'
    redirect_authenticated_user = True


def get_persian_months():
    return {i: jdatetime.date(1, i, 1).strftime('%B') for i in range(1, 13)}


def filter_queryset_by_month(request, queryset, date_field):
    selected_month = request.GET.get('month')
    if selected_month and selected_month.isdigit():
        month = int(selected_month)
        current_year = jdatetime.date.today().year
        start_date_jalali = jdatetime.date(current_year, month, 1)
        if month < 12:
            end_date_jalali = jdatetime.date(current_year, month + 1, 1)
        else:
            end_date_jalali = jdatetime.date(current_year + 1, 1, 1)

        start_date_gregorian = start_date_jalali.togregorian()
        end_date_gregorian = end_date_jalali.togregorian()

        filter_kwargs = {
            f'{date_field}__gte': start_date_gregorian,
            f'{date_field}__lt': end_date_gregorian,
        }
        return queryset.filter(**filter_kwargs)
    return queryset


@login_required
def financial_report_view(request):
    # Base querysets
    expenses_base = Expense.objects.filter(creator=request.user)
    other_incomes_base = OtherIncome.objects.filter(creator=request.user)
    customers_base = Customer.objects.filter(creator=request.user, status='success')

    # Filtered querysets for main stats
    expenses_stats = filter_queryset_by_month(request, expenses_base, 'spending_date')
    other_incomes_stats = filter_queryset_by_month(request, other_incomes_base, 'deposit_date')
    customer_incomes_stats = filter_queryset_by_month(request, customers_base, 'payment_date')

    # Main stats calculations
    total_customer_income = customer_incomes_stats.aggregate(total=Sum('price'))['total'] or 0
    total_other_income = other_incomes_stats.aggregate(total=Sum('price'))['total'] or 0
    total_income = total_customer_income + total_other_income
    total_expenses = expenses_stats.aggregate(total=Sum('price'))['total'] or 0
    net_profit = total_income - total_expenses

    # Today's stats
    today = timezone.now().date()
    today_income_q = \
        Customer.objects.filter(creator=request.user, status='success', payment_date=today).aggregate(
            total=Sum('price'))[
            'total'] or 0
    today_other_income_q = \
        OtherIncome.objects.filter(creator=request.user, deposit_date=today).aggregate(total=Sum('price'))['total'] or 0
    total_today_income = today_income_q + today_other_income_q
    total_today_expenses = \
        Expense.objects.filter(creator=request.user, spending_date=today).aggregate(total=Sum('price'))['total'] or 0

    # Line Chart Data
    timeframe = request.GET.get('timeframe', 'monthly')
    chart_labels = []
    income_data = []
    expense_data = []

    if timeframe == 'daily':
        days_range = 7
        date_range = [(today - timedelta(days=i)) for i in range(days_range - 1, -1, -1)]
        # ==================== FIX START ====================
        # استفاده از متد استاندارد strftime برای نمایش تاریخ شمسی
        chart_labels = [jdatetime.date.fromgregorian(date=d).strftime('%d %B') for d in date_range]
        # ===================== FIX END =====================
        for day in date_range:
            daily_income = (Customer.objects.filter(creator=request.user, status='success', payment_date=day).aggregate(
                s=Sum('price'))['s'] or 0) + (
                                       OtherIncome.objects.filter(creator=request.user, deposit_date=day).aggregate(
                                           s=Sum('price'))['s'] or 0)
            daily_expense = Expense.objects.filter(creator=request.user, spending_date=day).aggregate(s=Sum('price'))[
                                's'] or 0
            income_data.append(int(daily_income))
            expense_data.append(int(daily_expense))
    elif timeframe == 'weekly':
        weeks_range = 4
        chart_labels = []
        for i in range(weeks_range - 1, -1, -1):
            start_of_week = today - timedelta(days=today.weekday() + (i * 7))
            end_of_week = start_of_week + timedelta(days=6)
            start_jalali = jdatetime.date.fromgregorian(date=start_of_week).strftime('%d')
            end_jalali = jdatetime.date.fromgregorian(date=end_of_week).strftime('%d %B')
            chart_labels.append(f"{_('Week')} {start_jalali} - {end_jalali}")
            weekly_income = (Customer.objects.filter(creator=request.user, status='success',
                                                     payment_date__range=[start_of_week, end_of_week]).aggregate(
                s=Sum('price'))['s'] or 0) + (OtherIncome.objects.filter(creator=request.user,
                                                                         deposit_date__range=[start_of_week,
                                                                                              end_of_week]).aggregate(
                s=Sum('price'))['s'] or 0)
            weekly_expense = \
            Expense.objects.filter(creator=request.user, spending_date__range=[start_of_week, end_of_week]).aggregate(
                s=Sum('price'))['s'] or 0
            income_data.append(int(weekly_income))
            expense_data.append(int(weekly_expense))
    else:  # monthly (default)
        days_range = 30
        date_range = [(today - timedelta(days=i)) for i in range(days_range - 1, -1, -1)]
        # ==================== FIX START ====================
        # استفاده از متد استاندارد strftime برای نمایش تاریخ شمسی
        chart_labels = [jdatetime.date.fromgregorian(date=d).strftime('%d %B') for d in date_range]
        # ===================== FIX END =====================
        for day in date_range:
            daily_income = (Customer.objects.filter(creator=request.user, status='success', payment_date=day).aggregate(
                s=Sum('price'))['s'] or 0) + (
                                       OtherIncome.objects.filter(creator=request.user, deposit_date=day).aggregate(
                                           s=Sum('price'))['s'] or 0)
            daily_expense = Expense.objects.filter(creator=request.user, spending_date=day).aggregate(s=Sum('price'))[
                                's'] or 0
            income_data.append(int(daily_income))
            expense_data.append(int(daily_expense))

    # Expense Analysis
    top_expenses = expenses_stats.values('issue').annotate(total=Sum('price'), count=Count('issue')).order_by('-total')[
        :15]

    # Recent Activities
    recent_customers = Customer.objects.filter(creator=request.user).order_by('-created_at')[:5]
    recent_expenses = Expense.objects.filter(creator=request.user).order_by('-created_at')[:5]
    recent_incomes = OtherIncome.objects.filter(creator=request.user).order_by('-created_at')[:5]
    recent_activities = sorted(
        chain(recent_customers, recent_expenses, recent_incomes),
        key=attrgetter('created_at'),
        reverse=True
    )[:5]

    # Form handling
    if request.method == 'POST':
        if 'add_expense' in request.POST:
            expense_form = ExpenseForm(request.POST)
            if expense_form.is_valid():
                expense = expense_form.save(commit=False)
                expense.creator = request.user
                expense.save()
                messages.success(request, _("Expense added successfully."))
                return redirect(request.get_full_path())
        elif 'add_other_income' in request.POST:
            other_income_form = OtherIncomeForm(request.POST)
            if other_income_form.is_valid():
                income = other_income_form.save(commit=False)
                income.creator = request.user
                income.save()
                messages.success(request, _("Income added successfully."))
                return redirect(request.get_full_path())

    expense_form = ExpenseForm()
    other_income_form = OtherIncomeForm()

    context = {
        'expense_form': expense_form, 'other_income_form': other_income_form,
        'expenses': expenses_stats.order_by('-spending_date'),
        'other_incomes': other_incomes_stats.order_by('-deposit_date'),
        'months': get_persian_months(), 'selected_month': request.GET.get('month'),
        'total_income': total_income, 'total_expenses': total_expenses,
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


@login_required
def customer_dashboard_view(request):
    customers_base = Customer.objects.filter(creator=request.user)

    # FINAL FIX: A more robust way to get a unique, sorted list of non-empty referrers.
    referrer_list = Customer.objects.filter(creator=request.user).exclude(referrer__exact='').order_by(
        'referrer').values_list('referrer', flat=True).distinct()

    selected_referrer = request.GET.get('referrer')
    if selected_referrer:
        customers_base = customers_base.filter(referrer=selected_referrer)

    selected_status = request.GET.get('status')
    if selected_status in ['success', 'pending']:
        customers_base = customers_base.filter(status=selected_status)

    customers = filter_queryset_by_month(request, customers_base, 'payment_date')

    stats_queryset = customers
    total_giga = stats_queryset.aggregate(total=Sum('giga'))['total'] or 0
    paid_amount = stats_queryset.filter(status='success').aggregate(total=Sum('price'))['total'] or 0
    unpaid_amount = stats_queryset.filter(status='pending').aggregate(total=Sum('price'))['total'] or 0

    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.creator = request.user
            customer.save()
            messages.success(request, _("Customer '{name}' added successfully.").format(name=customer.name))
            return redirect(request.get_full_path())
    else:
        form = CustomerForm()

    context = {
        'form': form, 'customers': customers.order_by('-created_at'),
        'total_giga': total_giga,
        'paid_amount': paid_amount,
        'unpaid_amount': unpaid_amount,
        'months': get_persian_months(), 'selected_month': request.GET.get('month'),
        'referrer_list': referrer_list,
        'selected_referrer': selected_referrer,
        'selected_status': selected_status,
    }
    return render(request, 'dashboard/customer_dashboard.html', context)


@login_required
def edit_customer(request, pk):
    customer = get_object_or_404(Customer, id=pk, creator=request.user)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, _("Customer '{name}' updated successfully.").format(name=customer.name))
            return redirect('customer_dashboard')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'dashboard/edit_customer.html', {'form': form, 'customer': customer})


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
            return redirect('profile')

        if 'change_password' in request.POST and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, _('Password changed successfully.'))
            return redirect('profile')

        if 'change_avatar' in request.POST and profile_form.is_valid():
            profile_form.save()
            messages.success(request, _('Your avatar was successfully updated!'))
            return redirect('profile')

    else:
        user_form = UserProfileForm(instance=request.user)
        password_form = CustomPasswordChangeForm(user=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    context = {'user_form': user_form, 'password_form': password_form, 'profile_form': profile_form}
    return render(request, 'dashboard/profile.html', context)


@login_required
def set_theme_view(request):
    if request.method == 'POST':
        theme = request.POST.get('theme')
        if theme in ['light', 'dark']:
            profile, created = Profile.objects.get_or_create(user=request.user)
            profile.theme = theme
            profile.save()
            return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def delete_customer(request, pk):
    customer = get_object_or_404(Customer, id=pk, creator=request.user)
    if request.method == 'POST':
        messages.success(request, _("Customer '{name}' deleted successfully.").format(name=customer.name))
        customer.delete()
    return redirect('customer_dashboard')


@login_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, id=pk, creator=request.user)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, _("Expense deleted successfully."))
    return redirect('financial_report')


@login_required
def delete_other_income(request, pk):
    income = get_object_or_404(OtherIncome, id=pk, creator=request.user)
    if request.method == 'POST':
        income.delete()
        messages.success(request, _("Income deleted successfully."))
    return redirect('financial_report')


# --- ویوهای جدید برای ایمپورت و اکسپورت ---

@login_required
def import_export_view(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        file = request.FILES['csv_file']

        if not file.name.endswith('.csv'):
            messages.error(request, _("File is not a CSV type."))
            return redirect('import_export')

        try:
            df = pd.read_csv(file)
            df = df.where(pd.notna(df), None)  # تبدیل مقادیر NaN به None
            errors = []
            count = 0

            for index, row in df.iterrows():
                try:
                    payment_date_gregorian = None
                    if row.get('Date of deposit'):
                        jalali_date_str = str(row['Date of deposit'])
                        parts = list(map(int, jalali_date_str.split('/')))
                        payment_date_gregorian = jdatetime.date(parts[0], parts[1], parts[2]).togregorian()

                    status_val = 'pending'
                    check_val = str(row.get('Check', 'false')).lower()
                    if check_val in ['true', '1', 'yes']:
                        status_val = 'success'

                    Customer.objects.update_or_create(
                        name=row['User'],
                        creator=request.user,
                        defaults={
                            'expire_date': pd.to_datetime(row.get('Date expaire')).date() if row.get(
                                'Date expaire') else None,
                            'price': int(row.get('Price', 0)),
                            'giga': int(row.get('GB', 0)),
                            'phone_number': str(row.get('NUMBER PHONE', '')) if row.get('NUMBER PHONE') else '',
                            'payment_date': payment_date_gregorian,
                            'referrer': str(row.get('refrale', '')) if row.get('refrale') else '',
                            'bank_name': str(row.get('Bank Name', '')) if row.get('Bank Name') else '',
                            'status': status_val
                        }
                    )
                    count += 1
                except Exception as e:
                    errors.append(f"Row {index + 2}: {row.get('User')} - {e}")

            if errors:
                for error in errors: messages.error(request, error)
            if count > 0:
                messages.success(request, _("{count} records imported or updated successfully.").format(count=count))

        except Exception as e:
            messages.error(request, f"Error processing file: {e}")

        return redirect('import_export')

    return render(request, 'dashboard/import_export.html')


@login_required
def export_customers_csv(request):
    queryset = Customer.objects.filter(creator=request.user)
    df = pd.DataFrame(list(
        queryset.values('name', 'expire_date', 'price', 'giga', 'phone_number', 'payment_date', 'status', 'referrer',
                        'bank_name')))
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="customers.csv"'
    df.to_csv(path_or_buf=response, index=False, encoding='utf-8-sig')
    return response

# NEW: Add these two views at the end of the file
def custom_404(request, exception):
    return render(request, '404.html', {}, status=404)

def custom_403(request, exception):
    return render(request, '403.html', {}, status=403)