from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language

urlpatterns = [
    # این آدرس‌ها خارج از الگوی زبان هستند تا همیشه ثابت باشند
    # مثلا آدرس پنل ادمین همیشه /admin/ خواهد بود
    path('admin/', admin.site.urls),
    path('i18n/', set_language, name='set_language'),
]

# تمام آدرس‌های اصلی برنامه که در dashboard.urls تعریف شده‌اند،
# حالا چند زبانه خواهند شد. مثلا: /fa/customers/ یا /en/customers/
urlpatterns += i18n_patterns(
    path('', include('dashboard.urls')),
    # اگر در آینده اپلیکیشن‌های دیگری اضافه کنید، آنها را هم اینجا قرار دهید
)

