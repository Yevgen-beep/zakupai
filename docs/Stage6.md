# Stage 6 Monitoring Skeleton

## Цепочка сигналов

Prometheus -> Loki -> Grafana -> Alertmanager

## Чеклист развертывания

- [ ] Scrape configs обновлены для ключевых сервисов и Prometheus
- [ ] /metrics эндпоинты доступны для gateway, risk-engine, calc-service
- [ ] Базовые Grafana dashboards подключены и отображают данные
- [ ] Alertmanager получает алерты и маршрутизирует уведомления

## Укрепление безопасности

- Использовать Vault для хранения секретов и токенов мониторинга
- Включить mTLS между Prometheus, Loki, Grafana и сервисами
- Настроить logrotate для локальных логов и ротации Promtail

## Alertmanager

- [ ] Конфигурация alertmanager.yml проверена (`amtool check-config`)
- [ ] Интеграция с Prometheus targets
- [ ] Подключение к внешнему webhook/Slack/Telegram

## Бизнес-метрики

- zakupai_lots_total - общее количество разыгрываемых лотов
- zakupai_anti_dumping_flags_total - количество антидемпинговых флагов

## CI/CD

Добавить job `monitoring-check`, который валидирует конфигурации Prometheus, Loki и Alertmanager в пайплайне Stage 6.
