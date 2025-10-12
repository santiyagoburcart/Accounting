from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    CustomLoginView, customer_dashboard_view, delete_customer, edit_customer,
    profile_view, financial_report_view, delete_expense, delete_other_income,
    set_theme_view,
    # ویوهای جدید برای ایمپورت و اکسپورت وارد می‌شوند
    import_export_view,
    export_customers_csv
)

urlpatterns = [
    # این آدرس‌ها خارج از الگوی زبان هستند تا همیشه ثابت باشند
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    # صفحات اصلی
    path('', financial_report_view, name='financial_report'),
    path('customers/', customer_dashboard_view, name='customer_dashboard'),

    # عملیات مربوط به مشتریان
    path('customers/delete/<int:pk>/', delete_customer, name='delete_customer'),
    path('customers/edit/<int:pk>/', edit_customer, name='edit_customer'),

    # پروفایل و تنظیمات
    path('profile/', profile_view, name='profile'),
    path('set-theme/', set_theme_view, name='set_theme'),

    # عملیات مربوط به امور مالی
    path('expense/delete/<int:pk>/', delete_expense, name='delete_expense'),
    path('other-income/delete/<int:pk>/', delete_other_income, name='delete_other_income'),

    # --- مسیرهای جدید برای ایمپورت و اکسپورت ---
    path('tools/import-export/', import_export_view, name='import_export'),
    # FIX: The name is changed to 'export_customers_csv' to match the template and fix the NoReverseMatch error.
    path('tools/export/customers/', export_customers_csv, name='export_customers_csv'),
]