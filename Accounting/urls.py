from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language
# کدهای جدید برای نمایش فایل‌های رسانه
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # این آدرس‌ها خارج از الگوی زبان هستند تا همیشه ثابت باشند
    path('admin/', admin.site.urls),
    path('i18n/', set_language, name='set_language'),
]

# تمام آدرس‌های اصلی برنامه که در dashboard.urls تعریف شده‌اند،
# حالا چند زبانه خواهند شد.
urlpatterns += i18n_patterns(
    path('', include('dashboard.urls')),
)

# این بخش جدید به جنگو اجازه می‌دهد فایل‌های آپلود شده (مانند آواتار)
# را در حالت توسعه (DEBUG=True) نمایش دهد.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# NEW: Add these lines to handle 404 and 403 errors
handler404 = 'django.views.defaults.page_not_found'
handler403 = 'django.views.defaults.permission_denied'