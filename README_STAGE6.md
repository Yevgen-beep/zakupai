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
