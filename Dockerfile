FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# نصب پیش‌نیازهای سیستمی برای MySQL و کامپایلرها
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# نصب پکیج‌های پایتون
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# کپی کل پروژه
COPY . /app/
