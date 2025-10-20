# Accounting/dashboard/urls.py

from django.urls import path
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
    add_transaction_view, # <-- ایمپورت جدید
)

app_name = 'dashboard'

urlpatterns = [
    # ** مسیر جدید برای صفحه ورود تراکنش **
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
]