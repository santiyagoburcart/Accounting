# Accounting/dashboard/urls.py

from django.urls import path, include
from .views import (
    subscription_dashboard_view,
    financial_report_view,
    profile_view,
    set_theme_view,
    delete_expense,
    delete_other_income,
    customer_profile_list_view,
    edit_customer_profile,
    delete_customer_profile,
    bank_account_list_view,
    bank_account_edit_view,
    bank_account_delete_view,
    subscription_edit_view,
    subscription_delete_view,
    add_transaction_view,
    expense_edit_view,
    other_income_edit_view,
    get_customer_details,
    backup_panel,
    download_backup,
    telegram_backup,
    restore_db,
    main_dashboard_view,
    bank_report_view,
)

# --- ایمپورت‌های بخش موبایل ---
from dashboard.views.mobile import (
    mobile_home_view,
    mobile_transaction_list_view,
    mobile_add_transaction_view,
    mobile_edit_expense_view,
    mobile_delete_expense_view,
    mobile_edit_subscription_view,
    mobile_delete_subscription_view,
    mobile_edit_income_view,
    mobile_delete_income_view,

    mobile_menu_view,
    mobile_profile_view,

    mobile_backup_view,
    mobile_financial_report_view,

    mobile_bank_list_view,
    mobile_bank_add_view,
    mobile_bank_edit_view,
    mobile_bank_delete_view,

    mobile_customer_list_view,
    mobile_customer_add_view,
    mobile_customer_edit_view,
    mobile_customer_delete_view,
    mobile_change_password_view,


)

app_name = 'dashboard'

urlpatterns = [

    # ==============================
    # 📱 Mobile URLs (بخش موبایل)
    # ==============================
    path('mobile/home/', mobile_home_view, name='mobile_home'),

    # لیست تراکنش‌ها (نام این لینک باید با دکمه‌های بازگشت در HTML یکی باشد)
    path('mobile/transactions/', mobile_transaction_list_view, name='mobile_transaction_list'),

    # افزودن تراکنش در موبایل
    path('mobile/add/', mobile_add_transaction_view, name='mobile_add_transaction'),
    # زیرمجموعه‌های منو
    path('mobile/menu/', mobile_menu_view, name='mobile_menu'),

    path('mobile/profile/', mobile_profile_view, name='mobile_profile'),
    path('mobile/banks/', mobile_bank_list_view, name='mobile_bank_list'),
    path('mobile/backup/', mobile_backup_view, name='mobile_backup'),
    path('mobile/reports/', mobile_financial_report_view, name='mobile_financial_report'),

    path('mobile/profile/password/', mobile_change_password_view, name='mobile_change_password'),

    # Mobile Customers (Users)
    path('mobile/customers/', mobile_customer_list_view, name='mobile_customer_list'),
    path('mobile/customers/add/', mobile_customer_add_view, name='mobile_customer_add'),
    path('mobile/customers/<int:pk>/edit/', mobile_customer_edit_view, name='mobile_customer_edit'),
    path('mobile/customers/<int:pk>/delete/', mobile_customer_delete_view, name='mobile_customer_delete'),


    # Bank Management
    path('mobile/banks/', mobile_bank_list_view, name='mobile_bank_list'),
    path('mobile/banks/add/', mobile_bank_add_view, name='mobile_bank_add'),
    path('mobile/banks/<int:pk>/edit/', mobile_bank_edit_view, name='mobile_bank_edit'),
    path('mobile/banks/<int:pk>/delete/', mobile_bank_delete_view, name='mobile_bank_delete'),


    # --- Actions: Edit & Delete (لینک‌های جدید که ارور داشتند) ---
    path('mobile/expense/edit/<int:pk>/', mobile_edit_expense_view, name='mobile_edit_expense'),
    path('mobile/expense/delete/<int:pk>/', mobile_delete_expense_view, name='mobile_delete_expense'),

    path('mobile/income/<int:pk>/edit/', mobile_edit_income_view, name='mobile_edit_income'),
    path('mobile/income/<int:pk>/delete/', mobile_delete_income_view, name='mobile_delete_income'),

    path('mobile/sub/edit/<int:pk>/', mobile_edit_subscription_view, name='mobile_edit_subscription'),
    path('mobile/sub/delete/<int:pk>/', mobile_delete_subscription_view, name='mobile_delete_subscription'),

    # ==============================
    # 💻 Desktop URLs (بخش دسکتاپ)
    # ==============================
    path('transactions/add/', add_transaction_view, name='add_transaction'),

    # URLs for Subscriptions
    path('subscriptions/', subscription_dashboard_view, name='subscription_dashboard'),
    path('subscriptions/<int:pk>/edit/', subscription_edit_view, name='subscription_edit'),
    path('subscriptions/<int:pk>/delete/', subscription_delete_view, name='subscription_delete'),

    # URLs for Customers
    path('customers/', customer_profile_list_view, name='customer_profile_list'),
    path('customers/<int:pk>/edit/', edit_customer_profile, name='edit_customer_profile'),
    path('customers/<int:pk>/delete/', delete_customer_profile, name='delete_customer_profile'),

    # URLs for Bank Accounts
    path('bank-accounts/', bank_account_list_view, name='bank_account_list'),
    path('bank-accounts/<int:pk>/edit/', bank_account_edit_view, name='bank_account_edit'),
    path('bank-accounts/<int:pk>/delete/', bank_account_delete_view, name='bank_account_delete'),

    # Other URLs
    path('financial-report/', financial_report_view, name='financial_report'),
    path('profile/', profile_view, name='profile'),
    path('set-theme/', set_theme_view, name='set_theme'),
    path('expense/<int:pk>/delete/', delete_expense, name='delete_expense'),
    path('income/<int:pk>/delete/', delete_other_income, name='delete_other_income'),

    path('expense/<int:pk>/edit/', expense_edit_view, name='expense_edit'),
    path('income/<int:pk>/edit/', other_income_edit_view, name='other_income_edit'),

    # AJAX URLs
    path('ajax/get-customer-details/', get_customer_details, name='get_customer_details'),

    # backup url
    path('backup/panel/', backup_panel, name='backup_panel'),
    path('backup/download/', download_backup, name='backup_download'),
    path('backup/telegram/', telegram_backup, name='backup_telegram'),
    path('backup/restore/', restore_db, name='backup_restore'),

    # Main Dashboard (New Home)
    path('', main_dashboard_view, name='main_dashboard'),

    path('bank-report/', bank_report_view, name='bank_report'),

    path('', include('pwa.urls')),
]