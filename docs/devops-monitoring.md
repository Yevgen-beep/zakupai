# DevOps и Monitoring

## Обзор

ZakupAI использует полный стек мониторинга и наблюдаемости на базе Prometheus, Grafana и Alertmanager. Система собирает метрики с контейнеров, хостов, HTTP эндпоинтов и бизнес-логики для обеспечения надежности в продакшене.

## Архитектура мониторинга

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                             │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│ │   Grafana   │ │ Alertmanager│ │ Prometheus  │                 │
│ │   :3001     │ │    :9093    │ │    :9090    │                 │
│ └─────────────┘ └─────────────┘ └──────┬──────┘                 │
│                                        │                        │
├────────────────────────────────────────┼────────────────────────┤
│                   Exporters            │                        │
│ ┌─────────────┐ ┌─────────────┐ ┌──────▼──────┐                 │
│ │  cAdvisor   │ │ Node        │ │ BlackBox    │                 │
│ │   :8081     │ │ Exporter    │ │ Exporter    │                 │
│ │             │ │   :9100     │ │   :9115     │                 │
│ └─────────────┘ └─────────────┘ └─────────────┘                 │
├─────────────────────────────────────────────────────────────────┤
│                  ZakupAI Services                               │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│ │ Calc        │ │ Risk        │ │ Doc         │                 │
│ │ Service     │ │ Engine      │ │ Service     │                 │
│ │ /metrics    │ │ /metrics    │ │ /metrics    │                 │
│ └─────────────┘ └─────────────┘ └─────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

## Компоненты стека

### Prometheus (http://localhost:9090)

**Описание:** Система сбора и хранения метрик

**Конфигурация (`monitoring/prometheus/prometheus.yml`):**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # ZakupAI Services
  - job_name: 'calc-service'
    static_configs:
      - targets: ['calc-service:8000']
    metrics_path: /metrics

  - job_name: 'risk-engine'
    static_configs:
      - targets: ['risk-engine:8000']
    metrics_path: /metrics

  - job_name: 'doc-service'
    static_configs:
      - targets: ['doc-service:8000']
    metrics_path: /metrics

  - job_name: 'billing-service'
    static_configs:
      - targets: ['billing-service:8000']
    metrics_path: /metrics

  # Infrastructure
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  # HTTP Monitoring
  - job_name: 'blackbox'
    static_configs:
      - targets: ['blackbox-exporter:9115']

  - job_name: 'blackbox-http'
    static_configs:
      - targets:
        - http://gateway/health
        - http://calc-service:8000/health
        - http://risk-engine:8000/health
        - http://doc-service:8000/health
        - http://billing-service:8000/health
    metrics_path: /probe
    params:
      module: [http_2xx]
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

### Grafana (http://localhost:3001)

**Описание:** Визуализация метрик и дашборды

**Конфигурация (`monitoring/grafana/provisioning/`):**

#### Datasources (`datasources/prometheus.yml`)

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

#### Дашборды (`dashboards/`)

- **ZakupAI Overview** - общие метрики платформы
- **Services Health** - статус сервисов и HTTP проверки
- **Infrastructure** - метрики хоста и контейнеров
- **Billing Analytics** - использование API и лимиты

### Alertmanager (http://localhost:9093)

**Описание:** Управление алертами и уведомлениями

**Конфигурация (`monitoring/alertmanager/alertmanager.yml`):**

```yaml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@zakupai.site'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
- name: 'web.hook'
  webhook_configs:
  - url: 'http://telegram-notifier:8080/webhook'
    send_resolved: true

- name: 'critical'
  email_configs:
  - to: 'admin@zakupai.site'
    subject: '🚨 ZakupAI Critical Alert'
    body: |
      Alert: {{ .GroupLabels.alertname }}
      Summary: {{ .CommonAnnotations.summary }}
      Description: {{ .CommonAnnotations.description }}
```

## Метрики и экспортеры

### cAdvisor (:8081)

**Описание:** Метрики контейнеров Docker

**Ключевые метрики:**

```
# CPU использование контейнеров
container_cpu_usage_seconds_total

# Память контейнеров
container_memory_usage_bytes
container_memory_limit_bytes

# Сеть контейнеров
container_network_receive_bytes_total
container_network_transmit_bytes_total

# Файловая система
container_fs_usage_bytes
container_fs_limit_bytes
```

### Node Exporter (:9100)

**Описание:** Метрики операционной системы

**Ключевые метрики:**

```
# CPU
node_cpu_seconds_total
node_load1, node_load5, node_load15

# Память
node_memory_MemTotal_bytes
node_memory_MemFree_bytes
node_memory_Buffers_bytes
node_memory_Cached_bytes

# Диск
node_filesystem_size_bytes
node_filesystem_free_bytes
node_disk_io_now

# Сеть
node_network_receive_bytes_total
node_network_transmit_bytes_total
```

### BlackBox Exporter (:9115)

**Описание:** HTTP/HTTPS проверки доступности

**Модули конфигурации (`monitoring/blackbox.yml`):**

```yaml
modules:
  http_2xx:
    prober: http
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200]
      method: GET
      fail_if_ssl: false
      fail_if_not_ssl: false

  http_post:
    prober: http
    http:
      method: POST
      valid_status_codes: [200]
      body: '{"test": "probe"}'
      headers:
        Content-Type: application/json
```

**Ключевые метрики:**

```
# Доступность сервисов
probe_success

# Время ответа HTTP
probe_duration_seconds

# HTTP статус коды
probe_http_status_code

# SSL сертификаты
probe_ssl_earliest_cert_expiry
```

### ZakupAI Services Metrics

**Описание:** Бизнес-метрики приложений

**Кастомные метрики FastAPI сервисов:**

```python
# HTTP запросы
http_requests_total{method="POST", endpoint="/calc/margin", status="200"}

# Время обработки
http_request_duration_seconds{endpoint="/risk/score"}

# Ошибки приложения
app_errors_total{service="calc-service", error_type="validation"}

# Бизнес-метрики
zakupai_lot_analysis_total{type="risk_scoring"}
zakupai_document_generation_total{format="pdf"}
zakupai_api_key_validations_total{plan="premium", status="success"}
```

## Алерты

### Правила алертов (`monitoring/prometheus/alerts.yml`)

```yaml
groups:
- name: zakupai.rules
  rules:

  # Недоступность сервисов
  - alert: ServiceDown
    expr: probe_success == 0
    for: 30s
    labels:
      severity: critical
    annotations:
      summary: "Service {{ $labels.instance }} is down"
      description: "{{ $labels.instance }} has been down for more than 30 seconds."

  # Высокая нагрузка CPU
  - alert: HighCPUUsage
    expr: (100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)) > 80
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage on {{ $labels.instance }}"
      description: "CPU usage is above 80% for more than 2 minutes."

  # Мало свободной памяти
  - alert: HighMemoryUsage
    expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "High memory usage on {{ $labels.instance }}"
      description: "Memory usage is above 90%."

  # Мало места на диске
  - alert: DiskSpaceLow
    expr: (1 - (node_filesystem_free_bytes / node_filesystem_size_bytes)) * 100 > 85
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Low disk space on {{ $labels.instance }}"
      description: "Disk usage is above 85%."

  # Высокое время ответа HTTP
  - alert: HighResponseTime
    expr: probe_duration_seconds > 5
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "High response time for {{ $labels.instance }}"
      description: "Response time is above 5 seconds."

  # Превышение лимитов API
  - alert: APIRateLimitExceeded
    expr: rate(http_requests_total{status="429"}[5m]) > 0.1
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "API rate limit exceeded"
      description: "Rate limit exceeded on {{ $labels.endpoint }}."

  # Ошибки в Billing Service
  - alert: BillingServiceErrors
    expr: rate(billing_validation_errors_total[5m]) > 0.05
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Billing service validation errors"
      description: "High error rate in billing validations."
```

## Дашборды Grafana

### ZakupAI Overview Dashboard

```json
{
  "dashboard": {
    "title": "ZakupAI Platform Overview",
    "panels": [
      {
        "title": "Service Status",
        "type": "stat",
        "targets": [
          {
            "expr": "probe_success",
            "legendFormat": "{{ instance }}"
          }
        ]
      },
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{ service }} - {{ endpoint }}"
          }
        ]
      },
      {
        "title": "API Key Usage by Plan",
        "type": "piechart",
        "targets": [
          {
            "expr": "billing_usage_by_plan",
            "legendFormat": "{{ plan }}"
          }
        ]
      }
    ]
  }
}
```

### Infrastructure Dashboard

- **System Load** - load average 1/5/15 min
- **CPU Usage** - по ядрам и общее
- **Memory Usage** - используемая/свободная/cached
- **Disk Usage** - по разделам
- **Network Traffic** - входящий/исходящий трафик

### Services Health Dashboard

- **HTTP Status Codes** - 2xx/4xx/5xx по сервисам
- **Response Times** - P50/P95/P99 латенси
- **Error Rates** - ошибки приложений
- **Container Resources** - CPU/Memory контейнеров

## Бэкапы и отказоустойчивость

### Автоматические бэкапы PostgreSQL

**Скрипт (`backup/backup.sh`):**

```bash
#!/bin/bash

# Параметры
BACKUP_DIR="/backups"
POSTGRES_HOST="db"
POSTGRES_DB="zakupai"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="zakupai_backup_${DATE}.sql"

# Создание бэкапа
pg_dump -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB > $BACKUP_DIR/$BACKUP_FILE

# Сжатие
gzip $BACKUP_DIR/$BACKUP_FILE

# Загрузка в облако (Backblaze B2)
rclone copy $BACKUP_DIR/${BACKUP_FILE}.gz backblaze:zakupai-backups/

# Очистка старых бэкапов (старше 14 дней)
find $BACKUP_DIR -name "*.sql.gz" -mtime +14 -delete

echo "Backup completed: ${BACKUP_FILE}.gz"
```

**Cron расписание:**

```bash
# Ежедневные бэкапы в 2:00
0 2 * * * /opt/zakupai/backup/backup.sh

# Еженедельные полные бэкапы в воскресенье 1:00
0 1 * * 0 /opt/zakupai/backup/full_backup.sh
```

### Docker Health Checks

```yaml
services:
  calc-service:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
```

## Логирование

### Centralized Logging (Future)

```yaml
# ELK Stack для продакшена
services:
  elasticsearch:
    image: elasticsearch:8.8.0

  logstash:
    image: logstash:8.8.0

  kibana:
    image: kibana:8.8.0
    ports:
      - "5601:5601"
```

### Структурированные логи

```python
# JSON логи во всех сервисах
logging.basicConfig(
    format='{"ts":"%(asctime)s","level":"%(levelname)s","service":"calc-service","msg":"%(message)s","request_id":"%(request_id)s"}',
    level=logging.INFO
)
```

## Deployment мониторинга

### Запуск стека мониторинга

```bash
# Полный стек
docker-compose --profile monitoring up -d

# Только мониторинг
docker-compose up -d prometheus grafana alertmanager
```

### Проверка работы

```bash
# Статус сервисов мониторинга
curl http://localhost:9090/-/healthy    # Prometheus
curl http://localhost:3001/api/health   # Grafana
curl http://localhost:9093/-/healthy    # Alertmanager

# Метрики
curl http://localhost:9090/api/v1/query?query=up

# Targets
curl http://localhost:9090/api/v1/targets
```

## Production масштабирование

### High Availability

```yaml
# Кластер Prometheus
services:
  prometheus-1:
    image: prom/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--web.enable-admin-api'
      - '--web.enable-lifecycle'

  prometheus-2:
    image: prom/prometheus
    # Replica конфигурация
```

### External Storage

```yaml
# Long-term storage с Thanos
thanos-sidecar:
  image: thanosio/thanos:v0.31.0
  command:
    - 'sidecar'
    - '--tsdb.path=/prometheus'
    - '--objstore.config-file=/etc/thanos/bucket.yml'
```

## Заключение

Система мониторинга ZakupAI обеспечивает:

- ✅ **Полную наблюдаемость** - метрики сервисов, инфраструктуры и бизнес-процессов
- ✅ **Проактивные алерты** - уведомления о проблемах до их критичности
- ✅ **Визуализация** - дашборды для разных ролей (dev/ops/business)
- ✅ **Автоматические бэкапы** - надежность данных
- ✅ **Готовность к Production** - HA, внешнее хранение, централизованные логи
