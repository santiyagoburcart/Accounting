#!/bin/bash

# --- مسیر پروژه ---
PROJECT_DIR="/root/Accounting/Accounting"

# --- لود کردن متغیرها ---
if [ -f "$PROJECT_DIR/.env" ]; then
  export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
else
  echo "❌ Error: .env file not found at $PROJECT_DIR/.env"
  exit 1
fi

BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
CHAT_ID="$TELEGRAM_CHAT_ID"

# --- تنظیمات دیتابیس ---
CONTAINER_NAME="accounting-db"
DB_USER="$DB_USER"
DB_PASS="$DB_PASSWORD"
DB_NAME="$DB_NAME"

# --- مسیر فایل ---
BACKUP_DIR="/root/backups"
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
FILENAME="$BACKUP_DIR/$DB_NAME-$DATE.sql.gz"

mkdir -p $BACKUP_DIR

echo "1. Starting backup..."

# دستور بک‌اپ (با رفع مشکل دسترسی Tablespace)
docker exec -e MYSQL_PWD=$DB_PASS $CONTAINER_NAME /usr/bin/mysqldump -u $DB_USER --no-tablespaces $DB_NAME | gzip > "$FILENAME"

if [ ${PIPESTATUS[0]} -eq 0 ]; then
  echo "2. Backup created: $FILENAME"

  CAPTION="✅ Backup Successful%0A📅 Date: $DATE%0A🗄 DB: $DB_NAME"

  echo "3. Sending to Telegram..."

  # --- تغییر مهم اینجاست: نمایش خروجی تلگرام ---
  RESPONSE=$(curl -s -F chat_id=$CHAT_ID \
       -F document=@"$FILENAME" \
       -F caption="$CAPTION" \
       "https://api.telegram.org/bot$BOT_TOKEN/sendDocument")

  echo "Telegram Response: $RESPONSE"
  # ---------------------------------------------

  echo -e "\n4. Done!"
else
  echo "❌ Backup Failed!"
fi

find $BACKUP_DIR -type f -name "*.sql.gz" -mtime +7 -delete