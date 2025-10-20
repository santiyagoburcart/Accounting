# ===================================================
# Dockerfile for Django Accounting Project
# ===================================================

# 1. Base Image: استفاده از یک ایمیج پایتون سبک و بهینه
FROM python:3.10-slim-bullseye

# 2. Environment Variables: تنظیم متغیرهای محیطی برای عملکرد بهتر پایتون
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Create Working Directory: ساخت پوشه‌ای برای قرارگیری کدهای پروژه
WORKDIR /app

# 4. Install Dependencies: نصب کتابخانه‌های مورد نیاز
# ابتدا فقط فایل نیازمندی‌ها کپی می‌شود تا از کش داکر بهینه‌تر استفاده شود
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Project Code: کپی کردن تمام کدهای پروژه به داخل ایمیج
COPY . .

# 6. Collect Static Files: جمع‌آوری فایل‌های استاتیک جنگو
RUN python manage.py collectstatic --noinput

# 7. Expose Port: مشخص کردن پورتی که اپلیکیشن روی آن اجرا می‌شود
EXPOSE 8000

# 8. Run Application: دستور نهایی برای اجرای اپلیکیشن با Gunicorn
# این دستور 4 پروسه gunicorn را برای هندل کردن درخواست‌ها اجرا می‌کند
CMD ["gunicorn", "Accounting.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
