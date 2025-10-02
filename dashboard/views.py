from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils.translation import gettext as _
from .forms import (
    CustomerForm, UserProfileForm, CustomPasswordChangeForm,
    ExpenseForm, OtherIncomeForm
)
from .models import Customer, Expense, OtherIncome
from django.db.models import Sum
import jdatetime

class CustomLoginView(LoginView):
    template_name = 'dashboard/login.html'
    redirect_authenticated_user = True

def get_persian_months():
    """یک دیکشنری از ماه‌های فارسی برمی‌گرداند"""
    return { i: jdatetime.date(1, i, 1).strftime('%B') for i in range(1, 13) }

def filter_queryset_by_month(request, queryset, date_field):
    """کوئری ست داده شده را بر اساس ماه انتخاب شده در درخواست فیلتر می‌کند"""
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
    """ویو اصلی برنامه که گزارش مالی را نمایش می‌دهد"""
    # کوئری‌های پایه
    expenses_base = Expense.objects.filter(creator=request.user)
    other_incomes_base = OtherIncome.objects.filter(creator=request.user)
    customers_base = Customer.objects.filter(creator=request.user, is_paid=True)

    # فیلتر کردن داده‌ها بر اساس ماه
    expenses = filter_queryset_by_month(request, expenses_base, 'spending_date')
    other_incomes = filter_queryset_by_month(request, other_incomes_base, 'deposit_date')
    customer_incomes = filter_queryset_by_month(request, customers_base, 'payment_date')

    # محاسبات مالی
    total_customer_income = customer_incomes.aggregate(total=Sum('price'))['total'] or 0
    total_other_income = other_incomes.aggregate(total=Sum('price'))['total'] or 0
    total_income = total_customer_income + total_other_income
    total_expenses = expenses.aggregate(total=Sum('price'))['total'] or 0
    net_profit = total_income - total_expenses

    # مدیریت ثبت فرم‌ها
    if request.method == 'POST':
        if 'add_expense' in request.POST:
            expense_form = ExpenseForm(request.POST)
            if expense_form.is_valid():
                expense = expense_form.save(commit=False)
                expense.creator = request.user
                expense.save()
                messages.success(request, _("Expense added successfully."))
                # برای ماندن در همان ماه فیلتر شده
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
        'expenses': expenses, 'other_incomes': other_incomes,
        'months': get_persian_months(), 'selected_month': request.GET.get('month'),
        'total_income': total_income, 'total_expenses': total_expenses,
        'net_profit': net_profit,
    }
    return render(request, 'dashboard/financial_report.html', context)

@login_required
def customer_dashboard_view(request):
    """ویو جدید برای مدیریت مشتریان"""
    customers_base = Customer.objects.filter(creator=request.user)
    customers = filter_queryset_by_month(request, customers_base, 'created_at')
    stats_queryset = customers
    
    total_giga = stats_queryset.aggregate(total=Sum('giga'))['total'] or 0
    total_revenue = stats_queryset.filter(is_paid=True).aggregate(total=Sum('price'))['total'] or 0
    unpaid_amount = stats_queryset.filter(is_paid=False).aggregate(total=Sum('price'))['total'] or 0

    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.creator = request.user
            customer.save()
            messages.success(request, _("Customer '{name}' added successfully.").format(name=customer.name))
            return redirect('customer_dashboard')
    else:
        form = CustomerForm()

    context = {
        'form': form, 'customers': customers.order_by('-created_at'),
        'total_giga': total_giga, 'total_revenue': total_revenue,
        'paid_amount': total_revenue, 'unpaid_amount': unpaid_amount,
        'months': get_persian_months(), 'selected_month': request.GET.get('month'),
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
    user_form = UserProfileForm(instance=request.user)
    password_form = CustomPasswordChangeForm(user=request.user)
    if 'change_details' in request.POST:
        user_form = UserProfileForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, _('Profile details updated successfully.'))
            return redirect('profile')
    if 'change_password' in request.POST:
        password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, _('Password changed successfully.'))
            return redirect('profile')
        else:
            messages.error(request, _('Please correct the errors below.'))
    context = { 'user_form': user_form, 'password_form': password_form }
    return render(request, 'dashboard/profile.html', context)

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

