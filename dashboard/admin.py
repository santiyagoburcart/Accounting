from django.contrib import admin
from .models import  Expense, OtherIncome


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """
    تنظیمات نمایش مدل هزینه در پنل ادمین
    """
    list_display = ('issue', 'jalali_spending_date', 'price', 'is_server_cost', 'creator')
    list_filter = ('is_server_cost', 'spending_date', 'creator')
    search_fields = ('issue', 'description')
    list_per_page = 25

@admin.register(OtherIncome)
class OtherIncomeAdmin(admin.ModelAdmin):
    """
    تنظیمات نمایش مدل سایر درآمدها در پنل ادمین
    """
    list_display = ('name', 'jalali_deposit_date', 'price', 'creator')
    list_filter = ('deposit_date', 'creator')
    search_fields = ('name', 'description')
    list_per_page = 25