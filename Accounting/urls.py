# Accounting/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language
from django.conf import settings
from django.conf.urls.static import static

# ایمپورت‌های لازم برای لاگین و لاگ‌اوت
from django.contrib.auth import views as auth_views
from dashboard.views import CustomLoginView

# === بخش اول: URLهایی که چند زبانه نیستند ===
urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', set_language, name='set_language'),

    # URL های احراز هویت خارج از i18n قرار می‌گیرند تا همیشه ثابت باشند
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

# === بخش دوم: URLهایی که باید چند زبانه شوند ===
# تمام آدرس‌های داخل dashboard.urls حالا پیشوند /en/ یا /fa/ می‌گیرند
urlpatterns += i18n_patterns(
    path('', include('dashboard.urls')),
)

# بخش مربوط به نمایش فایل‌های مدیا در حالت توسعه
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# اصلاح هندلرهای خطا تا به ویوهای سفارشی شما اشاره کنند
handler404 = 'dashboard.views.custom_404'
handler403 = 'dashboard.views.custom_403'