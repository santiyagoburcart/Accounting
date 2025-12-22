import os
import requests
from django.shortcuts import render, redirect, get_object_or_404
from operator import attrgetter
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.contrib import messages
from django.utils.translation import gettext as _
from django.urls import reverse
from itertools import chain
import jdatetime
from datetime import datetime, timedelta, date
import subprocess # برای اجرای اسکریپت تلگرام
import gzip
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
import json
from django.utils import timezone
from django.core.management import call_command
from django.http import HttpResponse
from django.conf import settings
from django.core.files.storage import FileSystemStorage

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


# ایمپورت مدل‌ها و فرم‌ها
from dashboard.models import (
    Expense, OtherIncome, Subscription, CustomerProfile, BankAccount
)
from dashboard.forms import (
    ExpenseForm, OtherIncomeForm, SubscriptionForm,BankAccountForm,CustomerProfileForm
)


# ==========================================
# 1. صفحه خانه موبایل (Dashboard Summary)
# ==========================================
@login_required
def mobile_home_view(request):
    """
    نمایش کارت‌های آمار و تراکنش‌های اخیر با دیتای واقعی
    """
    user = request.user

    # --- 1. محاسبه موجودی کل (Total Balance) ---
    # موجودی کل = مجموع موجودی همه بانک‌ها
    banks = BankAccount.objects.filter(creator=user)
    total_balance = 0
    for bank in banks:
        # متد balance که قبلاً نوشتیم یا محاسبه دستی
        # اینجا محاسبه دستی می‌کنیم برای اطمینان
        inc = 0
        if hasattr(bank, 'other_incomes'):
            inc += bank.other_incomes.aggregate(s=Sum('price'))['s'] or 0
        elif hasattr(bank, 'otherincome_set'):
            inc += bank.otherincome_set.aggregate(s=Sum('price'))['s'] or 0

        sub = 0
        # چک کردن نام ریلیشن‌ها
        sub_manager = getattr(bank, 'subscriptions', None) or getattr(bank, 'subscription_set', None) or getattr(bank,
                                                                                                                 'subscription',
                                                                                                                 None)
        if sub_manager:
            sub = sub_manager.filter(status='success').aggregate(s=Sum('price'))['s'] or 0

        exp = 0
        exp_manager = getattr(bank, 'expenses', None) or getattr(bank, 'expense_set', None)
        if exp_manager:
            exp = exp_manager.aggregate(s=Sum('price'))['s'] or 0

        total_balance += (inc + sub) - exp

    # --- 2. محاسبه درآمد و هزینه ماه جاری ---
    today = jdatetime.date.today()
    start_month = jdatetime.date(today.year, today.month, 1).togregorian()
    # محاسبه پایان ماه
    if today.month < 12:
        end_month = jdatetime.date(today.year, today.month + 1, 1).togregorian() - timedelta(days=1)
    else:
        end_month = jdatetime.date(today.year + 1, 1, 1).togregorian() - timedelta(days=1)

    # کوئری‌های این ماه
    month_subs = \
    Subscription.objects.filter(creator=user, payment_date__range=(start_month, end_month), status='success').aggregate(
        s=Sum('price'))['s'] or 0
    month_other_inc = \
    OtherIncome.objects.filter(creator=user, deposit_date__range=(start_month, end_month)).aggregate(s=Sum('price'))[
        's'] or 0
    total_income_month = month_subs + month_other_inc

    total_expense_month = \
    Expense.objects.filter(creator=user, spending_date__range=(start_month, end_month)).aggregate(s=Sum('price'))[
        's'] or 0

    # --- 3. تراکنش‌های اخیر (Recent Activity) ---
    # 5 مورد آخر از هر کدام
    recent_expenses = Expense.objects.filter(creator=user).order_by('-spending_date')[:5]
    recent_incomes = OtherIncome.objects.filter(creator=user).order_by('-deposit_date')[:5]
    recent_subs = Subscription.objects.filter(creator=user, status='success').order_by('-payment_date')[:5]

    # یکسان‌سازی فیلد تاریخ برای مرتب‌سازی
    for r in recent_expenses: r.sort_date = r.spending_date
    for r in recent_incomes: r.sort_date = r.deposit_date
    for r in recent_subs: r.sort_date = r.payment_date

    # ادغام و مرتب‌سازی
    combined = sorted(
        chain(recent_expenses, recent_incomes, recent_subs),
        key=attrgetter('sort_date'),
        reverse=True
    )[:7]  # 7 تای آخر

    # تبدیل به فرمت مناسب تمپلیت
    recent_transactions = []
    for item in combined:
        if isinstance(item, Expense):
            recent_transactions.append({
                'type': 'expense',
                'title': item.issue or _("Expense"),
                'amount': item.price,
                'date': item.jalali_spending_date,
                'bank_name': item.source_bank.bank_name if item.source_bank else ''
            })
        elif isinstance(item, OtherIncome):
            recent_transactions.append({
                'type': 'income',
                'title': item.name or _("Income"),
                'amount': item.price,
                'date': item.jalali_deposit_date,
                'bank_name': item.destination_bank.bank_name if item.destination_bank else ''
            })
        elif isinstance(item, Subscription):
            recent_transactions.append({
                'type': 'sub',
                'title': item.customer.name,
                'amount': item.price,
                'date': item.jalali_payment_date,
                'bank_name': item.destination_bank.bank_name if item.destination_bank else ''
            })
    current_date_shamsi = jdatetime.date.today().strftime('%B %Y')  # مثلا: دی 1403
    context = {
        'total_balance': total_balance,
        'total_income': total_income_month,
        'total_expense': total_expense_month,
        'recent_transactions': recent_transactions,
        'current_date_display': current_date_shamsi
    }
    return render(request, 'dashboard/mobile/home.html', context)

# ==========================================
# 2. لیست تراکنش‌ها (Transactions List)
# ==========================================

@login_required
def mobile_transaction_list_view(request):
    filter_type = request.GET.get('type', 'all')
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', 'all')

    today = jdatetime.date.today()
    try:
        selected_year = int(request.GET.get('year', today.year))
        selected_month = int(request.GET.get('month', today.month))
    except ValueError:
        selected_year = today.year
        selected_month = today.month

    start_date_shamsi = jdatetime.date(selected_year, selected_month, 1)
    if selected_month < 12:
        end_date_shamsi = jdatetime.date(selected_year, selected_month + 1, 1) - timedelta(days=1)
    else:
        end_date_shamsi = jdatetime.date(selected_year + 1, 1, 1) - timedelta(days=1)

    start_gregorian = start_date_shamsi.togregorian()
    end_gregorian = end_date_shamsi.togregorian()

    expenses = Expense.objects.none()
    incomes = OtherIncome.objects.none()
    subs = Subscription.objects.none()

    stats = {'total_giga': 0, 'total_revenue': 0, 'paid_amount': 0, 'unpaid_amount': 0}

    if filter_type in ['all', 'expense']:
        expenses = Expense.objects.filter(creator=request.user, spending_date__range=(start_gregorian, end_gregorian))
        if search_query:
            expenses = expenses.filter(Q(issue__icontains=search_query) | Q(description__icontains=search_query))

    if filter_type in ['all', 'income']:
        incomes = OtherIncome.objects.filter(creator=request.user, deposit_date__range=(start_gregorian, end_gregorian))
        if search_query:
            incomes = incomes.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))

    if filter_type in ['all', 'sub']:
        all_subs_month = Subscription.objects.filter(creator=request.user, year=selected_year, month=selected_month)
        stats['total_giga'] = all_subs_month.aggregate(s=Sum('giga'))['s'] or 0
        stats['paid_amount'] = all_subs_month.filter(status='success').aggregate(s=Sum('price'))['s'] or 0
        stats['unpaid_amount'] = all_subs_month.filter(status='pending').aggregate(s=Sum('price'))['s'] or 0
        stats['total_revenue'] = stats['paid_amount'] + stats['unpaid_amount']

        subs = Subscription.objects.filter(creator=request.user, year=selected_year, month=selected_month)
        if status_filter == 'paid': subs = subs.filter(status='success')
        elif status_filter == 'unpaid': subs = subs.filter(status='pending')
        if search_query:
            subs = subs.filter(Q(customer__name__icontains=search_query) | Q(referrer__name__icontains=search_query))

    activity_list = []
    for item in expenses:
        activity_list.append({
            'id': item.id, 'type': 'expense',
            'title': item.issue or _("Expense"),
            'subtitle': item.source_bank.bank_name if item.source_bank else '',
            'amount': item.price,
            'date': item.jalali_spending_date,
            'is_income': False,
            'icon': 'fa-server' if item.is_server_cost else 'fa-bag-shopping',
        })
    for item in incomes:
        activity_list.append({
            'id': item.id, 'type': 'income',
            'title': item.name or _("Income"),
            'subtitle': item.destination_bank.bank_name if item.destination_bank else '',
            'amount': item.price,
            'date': item.jalali_deposit_date,
            'is_income': True,
            'icon': 'fa-arrow-down'
        })
    for item in subs:
        activity_list.append({
            'id': item.id, 'type': 'sub',
            'title': item.customer.name,
            'subtitle': f"{_('Ref')}: {item.referrer.name}" if item.referrer else _("Direct"),
            'amount': item.price,
            'date': item.jalali_payment_date,
            'is_income': True,
            'status': item.status,
            'icon': 'fa-crown'
        })

    activity_list.sort(key=lambda x: str(x['date']) if x['date'] else "0000/00/00", reverse=True)

    context = {
        'transactions': activity_list,
        'filter_type': filter_type,
        'status_filter': status_filter,
        'search_query': search_query,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'years_list': range(1402, 1406),
        'months_list': range(1, 13),
        'stats': stats,
    }
    return render(request, 'dashboard/mobile/transaction_list.html', context)


# ==========================================
# 3. افزودن تراکنش (Add Transaction)
# ==========================================
@login_required
def mobile_add_transaction_view(request):
    expense_form = ExpenseForm(prefix='expense')
    income_form = OtherIncomeForm(prefix='income')
    sub_form = SubscriptionForm(prefix='sub', user=request.user)

    if request.method == 'POST':
        if 'add_expense' in request.POST:
            form = ExpenseForm(request.POST, prefix='expense')
            if form.is_valid():
                obj = form.save(commit=False)
                obj.creator = request.user
                obj.save()
                messages.success(request, _("Expense added successfully."))
                return redirect('dashboard:mobile_add_transaction')
            else:
                expense_form = form

        elif 'add_other_income' in request.POST:
            form = OtherIncomeForm(request.POST, prefix='income')
            if form.is_valid():
                obj = form.save(commit=False)
                obj.creator = request.user
                obj.save()
                messages.success(request, _("Income added successfully."))
                return redirect('dashboard:mobile_add_transaction')
            else:
                income_form = form

        elif 'add_subscription' in request.POST:
            form = SubscriptionForm(request.POST, prefix='sub', user=request.user)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.creator = request.user
                obj.save()
                messages.success(request, _("Subscription added successfully."))
                return redirect('dashboard:mobile_add_transaction')
            else:
                sub_form = form

    context = {
        'expense_form': expense_form,
        'income_form': income_form,
        'sub_form': sub_form,
        'active_tab': 'expense'
    }
    return render(request, 'dashboard/mobile/add_transaction.html', context)


# --- EXPENSE ---
@login_required
def mobile_edit_expense_view(request, pk):
    obj = get_object_or_404(Expense, pk=pk, creator=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, _("Expense updated successfully."))
            return redirect('dashboard:mobile_transaction_list')
    else:
        form = ExpenseForm(instance=obj)

    context = {
        'form': form,
        'title': _("Edit Expense"),
        'action_url': request.path,
        'delete_url': reverse('dashboard:mobile_delete_expense', args=[pk]),
        'date_field_name': 'spending_date',
        # تبدیل تاریخ آبجکت به فرمت مناسب دیت پیکر (YYYY/MM/DD)
        'initial_date': str(obj.jalali_spending_date).replace('-','/') if obj.jalali_spending_date else '',
        'is_subscription': False
    }
    return render(request, 'dashboard/mobile/edit_generic.html', context)


@login_required
def mobile_delete_expense_view(request, pk):
    obj = get_object_or_404(Expense, pk=pk, creator=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, _("Expense deleted successfully."))
        return redirect('dashboard:mobile_transaction_list')

    context = {
        'item_title': obj.issue or _("Expense"),
    }
    return render(request, 'dashboard/mobile/confirm_delete.html', context)


# --- INCOME (NEW) ---
@login_required
def mobile_edit_income_view(request, pk):
    obj = get_object_or_404(OtherIncome, pk=pk, creator=request.user)
    if request.method == 'POST':
        form = OtherIncomeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, _("Income updated successfully."))
            return redirect('dashboard:mobile_transaction_list')
    else:
        form = OtherIncomeForm(instance=obj)

    context = {
        'form': form,
        'title': _("Edit Income"),
        'action_url': request.path,
        'delete_url': reverse('dashboard:mobile_delete_income', args=[pk]),
        'date_field_name': 'deposit_date',
        'initial_date': str(obj.jalali_deposit_date).replace('-','/') if obj.jalali_deposit_date else '',
        'is_subscription': False
    }
    return render(request, 'dashboard/mobile/edit_generic.html', context)

@login_required
def mobile_delete_income_view(request, pk):
    obj = get_object_or_404(OtherIncome, pk=pk, creator=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, _("Income deleted successfully."))
        return redirect('dashboard:mobile_transaction_list')

    context = {
        'item_title': obj.name or _("Income"),
    }
    return render(request, 'dashboard/mobile/confirm_delete.html', context)


# --- SUBSCRIPTION ---
@login_required
def mobile_edit_subscription_view(request, pk):
    obj = get_object_or_404(Subscription, pk=pk, creator=request.user)
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=obj, user=request.user)
        # دریافت مقدار تاگل استاتوس از ریکوئست (هندلینگ دستی برای اطمینان)
        status_value = request.POST.get('status', None)
        if status_value:
             # اگر فرم جنگو فیلد استاتوس را اورراید نکند، اینجا می‌توان دستی ست کرد
             # اما معمولا اینپوت هیدن کار را انجام می‌دهد
             pass

        if form.is_valid():
            form.save()
            messages.success(request, _("Subscription updated successfully."))
            return redirect('dashboard:mobile_transaction_list')
    else:
        form = SubscriptionForm(instance=obj, user=request.user)

    context = {
        'form': form,
        'title': _("Edit Subscription"),
        'action_url': request.path,
        'delete_url': reverse('dashboard:mobile_delete_subscription', args=[pk]),
        'date_field_name': 'payment_date',
        'initial_date': str(obj.jalali_payment_date).replace('-','/') if obj.jalali_payment_date else '',
        'is_subscription': True,
        'current_status': obj.status
    }
    return render(request, 'dashboard/mobile/edit_generic.html', context)


@login_required
def mobile_delete_subscription_view(request, pk):
    obj = get_object_or_404(Subscription, pk=pk, creator=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, _("Subscription deleted successfully."))
        return redirect('dashboard:mobile_transaction_list')

    context = {
        'item_title': f"{obj.customer.name} - {obj.price}",
    }
    return render(request, 'dashboard/mobile/confirm_delete.html', context)


@login_required
def mobile_menu_view(request):
    """
    نمایش منوی اصلی اپلیکیشن شامل لینک به بخش‌های مختلف
    """
    context = {
        'user': request.user,
        # اینجا بعداً می‌توانیم تعداد نوتیفیکیشن‌ها یا وضعیت‌های خاص را هم پاس بدهیم
    }
    return render(request, 'dashboard/mobile/menu.html', context)


# ==========================================
# 5. پروفایل کاربری (Profile Settings)
# ==========================================
@login_required
def mobile_profile_view(request):
    """
    ویرایش اطلاعات کاربر و آواتار
    """
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        # دریافت اطلاعات از فرم
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        avatar = request.FILES.get('avatar')

        # اعتبارسنجی و ذخیره
        try:
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.save()

            if avatar:
                # حذف آواتار قبلی اگر وجود دارد (اختیاری)
                profile.avatar = avatar

            profile.save()
            messages.success(request, _("Profile updated successfully."))
            return redirect('dashboard:mobile_profile')

        except Exception as e:
            messages.error(request, _("Error updating profile."))
            print(e)

    context = {
        'user': user,
        'title': _('Edit Profile')
    }
    return render(request, 'dashboard/mobile/profile.html', context)


# 8. Backup & Restore (SQL & Python-Telegram)
# ==========================================
@login_required
def mobile_backup_view(request):
    """
    مدیریت بکاپ (SQL برای دانلود و تلگرام) - اصلاح شده و نهایی
    """
    # تنظیمات دیتابیس
    db_settings = settings.DATABASES['default']
    DB_HOST = db_settings.get('HOST', 'localhost')
    DB_USER = db_settings.get('USER', '')
    DB_PASSWORD = db_settings.get('PASSWORD', '')
    DB_NAME = db_settings.get('NAME', '')

    # تنظیمات تلگرام
    BOT_TOKEN = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    CHAT_ID = getattr(settings, 'TELEGRAM_CHAT_ID', None)

    if request.method == 'POST':

        # ---------------------------------------------------------
        # A. دانلود مستقیم فایل SQL
        # ---------------------------------------------------------
        if 'create_backup' in request.POST:
            try:
                filename = f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql"

                # دستور mysqldump با --skip-ssl
                command = f"mysqldump --skip-ssl -h {DB_HOST} -u {DB_USER} -p'{DB_PASSWORD}' --no-tablespaces {DB_NAME}"

                process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, error = process.communicate()

                if process.returncode != 0:
                    messages.error(request, f"Backup Error: {error.decode('utf-8')}")
                    return redirect('dashboard:mobile_backup')

                response = HttpResponse(output, content_type='application/sql')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response

            except Exception as e:
                messages.error(request, f"System Error: {str(e)}")
                return redirect('dashboard:mobile_backup')

        # ---------------------------------------------------------
        # B. ارسال به تلگرام
        # ---------------------------------------------------------
        elif 'telegram_backup' in request.POST:
            if not BOT_TOKEN or not CHAT_ID:
                messages.error(request, "Error: Bot Token or Chat ID is missing in settings.")
                return redirect('dashboard:mobile_backup')

            try:
                raw_filename = f"/tmp/{DB_NAME}_raw.sql"
                zip_filename = f"/tmp/{DB_NAME}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql.gz"

                command = f"mysqldump --skip-ssl -h {DB_HOST} -u {DB_USER} -p'{DB_PASSWORD}' --no-tablespaces {DB_NAME}"

                with open(raw_filename, 'w') as f:
                    process = subprocess.Popen(command, shell=True, stdout=f, stderr=subprocess.PIPE)
                    # ✅ اصلاح مهم: استفاده از stdout_data به جای _
                    stdout_data, error = process.communicate()

                if process.returncode != 0:
                    messages.error(request, f"Dump Error: {error.decode('utf-8')}")
                    return redirect('dashboard:mobile_backup')

                with open(raw_filename, 'rb') as f_in:
                    with gzip.open(zip_filename, 'wb') as f_out:
                        f_out.writelines(f_in)

                caption = f"✅ Mobile Backup (SQL)\n📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n🗄 DB: {DB_NAME}"
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

                with open(zip_filename, 'rb') as f:
                    files = {'document': f}
                    data = {'chat_id': CHAT_ID, 'caption': caption}
                    response = requests.post(url, files=files, data=data)

                if os.path.exists(raw_filename): os.remove(raw_filename)
                if os.path.exists(zip_filename): os.remove(zip_filename)

                if response.status_code == 200 and response.json().get('ok'):
                    messages.success(request, _("Backup sent to Telegram successfully!"))
                else:
                    messages.error(request, f"Telegram API Error: {response.text}")

            except Exception as e:
                messages.error(request, f"Process Error: {str(e)}")

            return redirect('dashboard:mobile_backup')

        # ---------------------------------------------------------
        # C. ریستور (Restore)
        # ---------------------------------------------------------
        elif 'restore_backup' in request.POST and request.FILES.get('backup_file'):
            try:
                sql_file = request.FILES['backup_file']
                temp_path = f"/tmp/restore_{sql_file.name}"

                with open(temp_path, 'wb+') as destination:
                    for chunk in sql_file.chunks():
                        destination.write(chunk)

                # ✅ اصلاح قبلی: استفاده از --skip-ssl
                if temp_path.endswith('.gz'):
                    cmd = f"gunzip < {temp_path} | mysql --skip-ssl -h {DB_HOST} -u {DB_USER} -p'{DB_PASSWORD}' {DB_NAME}"
                else:
                    cmd = f"mysql --skip-ssl -h {DB_HOST} -u {DB_USER} -p'{DB_PASSWORD}' {DB_NAME} < {temp_path}"

                process = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                if os.path.exists(temp_path):
                    os.remove(temp_path)

                if process.returncode == 0:
                    messages.success(request, _("Database restored successfully."))
                else:
                    messages.error(request, f"Restore Failed: {process.stderr}")

            except Exception as e:
                messages.error(request, f"System Error: {str(e)}")

            return redirect('dashboard:mobile_backup')

    # ✅ حالا اینجا دیگر ارور نمی‌دهد چون متغیر _ در بالا استفاده نشده است
    return render(request, 'dashboard/mobile/backup.html', {'title': _('Database Backup')})


@login_required
def mobile_bank_list_view(request):
    """
    لیست بانک‌ها با قابلیت فیلتر تاریخ و نمایش آمار دقیق (Net Flow)
    """
    # 1. دریافت پارامترهای فیلتر (سال و ماه)
    current_date = jdatetime.date.today()
    selected_year = int(request.GET.get('year', current_date.year))
    selected_month = int(request.GET.get('month', current_date.month))

    # محاسبه بازه زمانی (تاریخ شروع و پایان ماه انتخاب شده به میلادی)
    start_shamsi = jdatetime.date(selected_year, selected_month, 1)
    if selected_month < 12:
        end_shamsi = jdatetime.date(selected_year, selected_month + 1, 1) - timedelta(days=1)
    else:
        end_shamsi = jdatetime.date(selected_year + 1, 1, 1) - timedelta(days=1)

    start_g = start_shamsi.togregorian()
    end_g = end_shamsi.togregorian()

    # لیست بانک‌ها
    banks = BankAccount.objects.filter(creator=request.user)

    total_net_flow = 0

    for bank in banks:
        # مدیریت نام ریلیشن‌ها (مثل قبل هوشمند)
        # 1. درآمدها (در بازه زمانی انتخاب شده)
        if hasattr(bank, 'other_incomes'):
            inc_manager = bank.other_incomes
        else:
            inc_manager = getattr(bank, 'otherincome_set', None)

        inc = inc_manager.filter(deposit_date__range=(start_g, end_g)).aggregate(s=Sum('price'))[
                  's'] or 0 if inc_manager else 0

        # 2. اشتراک‌ها (در بازه زمانی)
        if hasattr(bank, 'subscriptions'):
            sub_manager = bank.subscriptions
        elif hasattr(bank, 'subscription_set'):
            sub_manager = bank.subscription_set
        elif hasattr(bank, 'subscription'):
            sub_manager = bank.subscription
        else:
            sub_manager = None

        if sub_manager:
            sub = sub_manager.filter(status='success', payment_date__range=(start_g, end_g)).aggregate(s=Sum('price'))[
                      's'] or 0
        else:
            sub = 0

        # 3. هزینه‌ها (در بازه زمانی)
        if hasattr(bank, 'expenses'):
            exp_manager = bank.expenses
        else:
            exp_manager = getattr(bank, 'expense_set', None)

        exp = exp_manager.filter(spending_date__range=(start_g, end_g)).aggregate(s=Sum('price'))[
                  's'] or 0 if exp_manager else 0

        # محاسبات
        total_income = inc + sub
        net_flow = total_income - exp

        # ذخیره در آبجکت برای نمایش در تمپلیت
        bank.stat_income = total_income
        bank.stat_expense = exp
        bank.stat_net_flow = net_flow
        bank.stat_subs = sub
        bank.stat_other = inc

        total_net_flow += net_flow

    # ساخت لیست سال‌ها و ماه‌ها برای دراپ‌داون
    years = range(1402, 1406)
    months = range(1, 13)
    month_names = {
        1: 'Farvardin', 2: 'Ordibehesht', 3: 'Khordad', 4: 'Tir', 5: 'Mordad', 6: 'Shahrivar',
        7: 'Mehr', 8: 'Aban', 9: 'Azar', 10: 'Dey', 11: 'Bahman', 12: 'Esfand'
    }

    context = {
        'banks': banks,
        'total_net_flow': total_net_flow,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_month_name': month_names[selected_month],
        'years': years,
        'months': months,
        'month_names': month_names,
        'title': _('Bank Report')
    }
    return render(request, 'dashboard/mobile/bank_list.html', context)



@login_required
def mobile_bank_add_view(request):
    """ افزودن بانک جدید """
    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.creator = request.user
            obj.save()
            messages.success(request, _("Bank account added successfully."))
            return redirect('dashboard:mobile_bank_list')
    else:
        form = BankAccountForm()

    context = {
        'form': form,
        'title': _('Add New Bank'),
        'action_url': request.path
    }
    return render(request, 'dashboard/mobile/bank_form.html', context)


@login_required
def mobile_bank_edit_view(request, pk):
    """ ویرایش بانک """
    obj = get_object_or_404(BankAccount, pk=pk, creator=request.user)
    if request.method == 'POST':
        form = BankAccountForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, _("Bank account updated."))
            return redirect('dashboard:mobile_bank_list')
    else:
        form = BankAccountForm(instance=obj)

    context = {
        'form': form,
        'title': _('Edit Bank'),
        'action_url': request.path,
        'delete_url': reverse('dashboard:mobile_bank_delete', args=[pk])
    }
    return render(request, 'dashboard/mobile/bank_form.html', context)


@login_required
def mobile_bank_delete_view(request, pk):
    """ حذف بانک """
    obj = get_object_or_404(BankAccount, pk=pk, creator=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, _("Bank account deleted."))
        return redirect('dashboard:mobile_bank_list')

    context = {
        'item_title': obj.bank_name,
        'cancel_url': 'dashboard:mobile_bank_list'
    }
    return render(request, 'dashboard/mobile/confirm_delete.html', context)


@login_required
def mobile_financial_report_view(request):
    """ گزارشات مالی با نمودار """

    # 1. محاسبه دیتای 6 ماه اخیر برای نمودار خطی
    labels = []
    income_data = []
    expense_data = []

    today = jdatetime.date.today()
    current_month = today.month
    current_year = today.year

    # لوپ روی 6 ماه گذشته
    for i in range(5, -1, -1):
        m = current_month - i
        y = current_year
        if m <= 0:
            m += 12
            y -= 1

        # نام ماه
        month_name = jdatetime.date(y, m, 1).strftime('%B')
        labels.append(month_name)

        # محاسبه بازه تاریخ میلادی برای آن ماه
        start_shamsi = jdatetime.date(y, m, 1)
        if m < 12:
            end_shamsi = jdatetime.date(y, m + 1, 1) - timedelta(days=1)
        else:
            end_shamsi = jdatetime.date(y + 1, 1, 1) - timedelta(days=1)

        start_g = start_shamsi.togregorian()
        end_g = end_shamsi.togregorian()

        # جمع درآمدها (سایر + سابسکرایبشن)
        inc = OtherIncome.objects.filter(creator=request.user, deposit_date__range=(start_g, end_g)).aggregate(
            s=Sum('price'))['s'] or 0
        sub = Subscription.objects.filter(creator=request.user, payment_date__range=(start_g, end_g),
                                          status='success').aggregate(s=Sum('price'))['s'] or 0
        income_data.append(inc + sub)

        # جمع هزینه‌ها
        exp = \
        Expense.objects.filter(creator=request.user, spending_date__range=(start_g, end_g)).aggregate(s=Sum('price'))[
            's'] or 0
        expense_data.append(exp)

    # 2. آمار کلی برای نمودار دایره‌ای (کل دوران)
    total_income_all = sum(income_data)  # یا کوئری کلی
    total_expense_all = sum(expense_data)

    context = {
        'title': _('Financial Reports'),
        # تبدیل دیتا به JSON برای جاوااسکریپت
        'chart_labels': json.dumps(labels),
        'chart_income': json.dumps(income_data),
        'chart_expense': json.dumps(expense_data),
        'total_income': total_income_all,
        'total_expense': total_expense_all
    }
    return render(request, 'dashboard/mobile/reports.html', context)


# ==========================================
# 10. مدیریت مشتریان (Customer/Users Management)
# ==========================================

@login_required
def mobile_customer_list_view(request):
    """ لیست مشتریان (Users) """
    customers = CustomerProfile.objects.filter(creator=request.user).order_by('-created_at')

    # جستجو
    search_query = request.GET.get('q', '')
    if search_query:
        customers = customers.filter(name__icontains=search_query)

    context = {
        'customers': customers,
        'search_query': search_query,
        'title': _('Customers')
    }
    return render(request, 'dashboard/mobile/customer_list.html', context)


@login_required
def mobile_customer_add_view(request):
    """ افزودن مشتری جدید """
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.creator = request.user
            obj.save()
            messages.success(request, _("Customer added successfully."))
            return redirect('dashboard:mobile_customer_list')
    else:
        form = CustomerProfileForm()

    context = {
        'form': form,
        'title': _('Add Customer'),
        'action_url': request.path
    }
    return render(request, 'dashboard/mobile/edit_generic.html', context)  # استفاده از قالب عمومی ادیت


@login_required
def mobile_customer_edit_view(request, pk):
    """ ویرایش مشتری """
    obj = get_object_or_404(CustomerProfile, pk=pk, creator=request.user)
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, _("Customer updated."))
            return redirect('dashboard:mobile_customer_list')
    else:
        form = CustomerProfileForm(instance=obj)

    context = {
        'form': form,
        'title': _('Edit Customer'),
        'action_url': request.path,
        'delete_url': reverse('dashboard:mobile_customer_delete', args=[pk])
    }
    return render(request, 'dashboard/mobile/edit_generic.html', context)


@login_required
def mobile_customer_delete_view(request, pk):
    """ حذف مشتری """
    obj = get_object_or_404(CustomerProfile, pk=pk, creator=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, _("Customer deleted."))
        return redirect('dashboard:mobile_customer_list')

    context = {
        'item_title': obj.name,
        'cancel_url': 'dashboard:mobile_customer_list'
    }
    return render(request, 'dashboard/mobile/confirm_delete.html', context)


@login_required
def mobile_change_password_view(request):
    """
    Handles password change separately for better UX.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Important: Keep the user logged in after password change
            update_session_auth_hash(request, user)
            messages.success(request, _("Your password was successfully updated!"))
            return redirect('dashboard:mobile_profile')
        else:
            messages.error(request, _("Please correct the error below."))
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'dashboard/mobile/change_password.html', {
        'form': form,
        'title': _('Change Password')
    })