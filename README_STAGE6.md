# 📌 ZakupAI — Stage6 стабильный бэкап

## Ветка бэкапа

- **stable-28-09**
  Содержит полностью рабочую сборку Stage6 на 28.09.2025.
  Все основные сервисы оживлены и проверены:
  - 🌐 Gateway
  - ⚖️ Risk-engine
  - 🔢 Calc-service
  - 📥 ETL-service
  - 📄 Doc-service
  - 🧩 Embedding API
  - 💰 Billing-service (исправлен health endpoint)
  - 📊 Prometheus + Grafana + Alertmanager
  - 🔧 Node Exporter + cAdvisor
  - 📱 Web UI

## Сценарии запуска

```bash
# Перейти в стабильную ветку
git checkout stable-28-09

# Поднять Stage6 без очистки кэша
make stage6-up

# Тестовые проверки
./stage6-smoke.sh
./stage6-debug.sh
```

### Monitoring & Security

- Для уведомлений Alertmanager в Telegram заполните секцию `# --- Telegram Alerts ---` в корневом `.env` (или `.env.stage`) значениями `TELEGRAM_BOT_TOKEN` и `TELEGRAM_ADMIN_ID`.
  Получите токен у [@BotFather](https://t.me/BotFather), а numeric ID администратора — через @userinfobot или `https://api.telegram.org/bot<token>/getUpdates`.
- После обновления `.env` перезапустите мониторинговый стек (`make stage6-monitoring-up` / соответствующий docker compose), чтобы `alertmanager-bot` подхватил новые переменные.
- Цель `make stage6-monitoring-up` проверяет, что значения не оставлены `changeme`/`CHANGE_IN_PRODUCTION`; при незаполненных токенах запуск прервётся с ошибкой.
