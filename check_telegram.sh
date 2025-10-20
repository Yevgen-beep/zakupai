#!/usr/bin/env bash
set -euo pipefail

# Загружаем токен и admin_id из .env
if [ -f .env ]; then
  export $(grep TELEGRAM_BOT_TOKEN .env | xargs)
  export $(grep TELEGRAM_ADMIN_ID .env | xargs)
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "❌ TELEGRAM_BOT_TOKEN не найден в .env"
  exit 1
fi

echo "🔑 Проверка токена..."
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" | jq

echo
echo "📩 Последние апдейты (ищи свой from.id для TELEGRAM_ADMIN_ID):"
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" | jq '.result[].message.from'
