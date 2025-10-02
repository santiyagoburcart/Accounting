from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    CustomLoginView, customer_dashboard_view, delete_customer, edit_customer, 
    profile_view, financial_report_view, delete_expense, delete_other_income
)

urlpatterns = [
    # این آدرس‌ها خارج از الگوی زبان هستند تا همیشه ثابت باشند
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    
    # صفحه اصلی جدید: گزارش مالی
    path('', financial_report_view, name='financial_report'),
    
    # صفحه جدید برای مدیریت مشتریان
    path('customers/', customer_dashboard_view, name='customer_dashboard'),
    
    # آدرس‌های مربوط به مشتریان
    path('customers/delete/<int:pk>/', delete_customer, name='delete_customer'),
    path('customers/edit/<int:pk>/', edit_customer, name='edit_customer'),
    
    # آدرس پروفایل
    path('profile/', profile_view, name='profile'),
    
    # آدرس‌های جدید برای حذف هزینه و درآمد
    path('expense/delete/<int:pk>/', delete_expense, name='delete_expense'),
    path('other-income/delete/<int:pk>/', delete_other_income, name='delete_other_income'),
]

