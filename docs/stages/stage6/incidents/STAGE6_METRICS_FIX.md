# Stage6 Monitoring - Исправление "No data" в Grafana

## 🔍 Диагностика проблемы

**Симптомы:**
- Prometheus targets: все UP ✅
- `http_requests_total` в Prometheus: пусто ❌
- Grafana dashboards: "No data" ❌

**Корневая причина:**
1. ✅ **Инструментация работает** - `prometheus_fastapi_instrumentator` установлен и настроен
2. ❌ **Нет трафика** - метрики Counter создаются только после ПЕРВОГО HTTP-запроса к сервису (кроме `/health` и `/metrics`, которые исключены из мониторинга)
3. ❌ **Неправильные label names** - Dashboard queries используют `service`, но метрики используют `job`

---

## ✅ Решение

### 1. Генерация трафика (обязательно!)

Метрики FastAPI появляются только **после первых запросов** к API endpoints:

```bash
# Разовая генерация
for port in 7001 7002 7003 7004 7005 7010 7011; do
  curl -s "http://localhost:$port/docs" >/dev/null 2>&1
done

# Или используйте готовый скрипт для непрерывной генерации
./stage6-continuous-traffic.sh
```

**Важно:** Эндпоинты `/health` и `/metrics` **не создают** метрики (они исключены в middleware). Используйте `/docs`, `/openapi.json` или любые API endpoints.

---

### 2. Исправление Dashboard Queries

**Файл:** [`monitoring/grafana/provisioning/dashboards/overview/zakupai-overview.json`](monitoring/grafana/provisioning/dashboards/overview/zakupai-overview.json)

#### До:
```json
"expr": "sum by (service) (rate(http_requests_total[5m]))"
```

#### После:
```json
"expr": "sum by (job) (irate(http_requests_total[2m]))"
```

**Изменения:**
- `service` → `job` (правильный label из метрик)
- `rate()` → `irate()` (мгновенный rate, работает с меньшим количеством точек)
- `[5m]` → `[2m]` (короче интервал для быстрой реакции)

---

### 3. Исправление Recording Rules

**Файл:** [`monitoring/prometheus/rules.yml`](monitoring/prometheus/rules.yml:29)

#### До:
```yaml
sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
```

#### После:
```yaml
sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job)
```

---

### 4. Применение изменений

```bash
# Перезапуск Prometheus с новыми rules
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  restart prometheus

# Перезапуск Grafana с новым dashboard
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  restart grafana

# Генерация трафика
./stage6-continuous-traffic.sh &
TRAFFIC_PID=$!

# Через 30-60 секунд проверяем Grafana
open http://localhost:3030/d/zakupai-overview
# Логин: admin / admin
```

---

## 📊 Проверка результатов

### 1. Проверить наличие метрик в Prometheus

```bash
# Должно вернуть > 0
curl -s 'http://localhost:9095/api/v1/query?query=http_requests_total' | \
  jq '.data.result | length'

# Должно показать счётчики по сервисам
curl -s 'http://localhost:9095/api/v1/query?query=sum(http_requests_total)by(job)' | \
  jq -r '.data.result[] | "\(.metric.job): \(.value[1])"'
```

**Ожидаемый output:**
```
calc-service: 163
risk-engine: 161
doc-service: 161
...
```

### 2. Проверить irate (мгновенный rate)

```bash
curl -s 'http://localhost:9095/api/v1/query?query=sum(irate(http_requests_total[2m]))by(job)' | \
  jq -r '.data.result[] | "\(.metric.job): \(.value[1])"'
```

**Должно показать rate (req/sec):**
```
calc-service: 0.5
risk-engine: 0.5
...
```

### 3. Проверить recording rules

```bash
# api_error_ratio (должен быть 0 если нет ошибок)
curl -s 'http://localhost:9095/api/v1/query?query=api_error_ratio' | \
  jq -r '.data.result[0].value[1]'

# Должно вернуть: 0
```

### 4. Открыть Grafana Dashboard

```
http://localhost:3030/d/zakupai-overview
```

**Ожидаемые панели:**
| Панель | Metric | Ожидаемое значение |
|--------|--------|--------------------|
| **Availability** | `(1 - avg(api_error_ratio)) * 100` | 100% (зелёный) |
| **Error Ratio** | `avg(api_error_ratio) * 100` | 0% (зелёный) |
| **Request Rate by Service** | `sum by (job) (irate(http_requests_total[2m]))` | Графики для всех сервисов |

---

## 🔧 Файлы изменённые

| Файл | Изменение | Причина |
|------|-----------|---------|
| [monitoring/grafana/provisioning/datasources/datasources.yml](monitoring/grafana/provisioning/datasources/datasources.yml:6) | `url: http://prometheus:9095` | Исправлен порт (был 9090) |
| [monitoring/grafana/provisioning/dashboards/overview/zakupai-overview.json](monitoring/grafana/provisioning/dashboards/overview/zakupai-overview.json:134) | `sum by (job) (irate(...))` | Исправлены label names + используем irate |
| [monitoring/prometheus/rules.yml](monitoring/prometheus/rules.yml:29) | `by (le, job)` | Исправлен label name |
| [monitoring/prometheus/prometheus.yml](monitoring/prometheus/prometheus.yml:114) | Vault target закомментирован | Убран шум (требует токена) |
| [stage6-continuous-traffic.sh](stage6-continuous-traffic.sh) | **NEW** | Скрипт для генерации трафика |

---

## 📝 Важные замечания

### О метриках FastAPI

1. **Counter metrics** (`http_requests_total`) создаются **только после первого запроса**
2. Эндпоинты `/health` и `/metrics` **исключены** из мониторинга (см. [zakupai_common/fastapi/metrics.py](libs/zakupai_common/zakupai_common/fastapi/metrics.py:25))
3. Для `rate()` нужно минимум **2 scrape cycles** с разными значениями (2 × 15s = 30s минимум)

### О Prometheus scrape

- **Scrape interval:** 15 секунд ([prometheus.yml:2](monitoring/prometheus/prometheus.yml:2))
- **Evaluation interval:** 15 секунд ([prometheus.yml:3](monitoring/prometheus/prometheus.yml:3))
- После генерации трафика подождите **30-45 секунд** для накопления данных

### О label names

Наши метрики используют labels:
- `job` - имя сервиса (calc-service, risk-engine, ...)
- `service` - короткое имя (calc, risk, ...) - добавляется middleware
- `endpoint` - HTTP path (/docs, /api/v1/calculate, ...)
- `method` - HTTP method (GET, POST, ...)
- `status_code` - HTTP status (200, 404, 500, ...)

**Dashboard queries должны использовать `job`**, а не `service`, т.к. Prometheus relabel использует `job`.

---

## 🚀 Быстрый старт (TL;DR)

```bash
# 1. Применить все изменения из этого документа
git diff  # проверьте изменения

# 2. Перезапустить мониторинг
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  restart prometheus grafana

# 3. Генерировать трафик (КРИТИЧНО!)
./stage6-continuous-traffic.sh &

# 4. Подождать 60 секунд
sleep 60

# 5. Открыть Grafana
open http://localhost:3030/d/zakupai-overview
# admin / admin

# 6. Проверить метрики
curl -s 'http://localhost:9095/api/v1/query?query=sum(irate(http_requests_total[2m]))by(job)' | jq
```

---

## 🐛 Если всё ещё "No data"

### 1. Проверьте Prometheus targets

```bash
curl -s http://localhost:9095/api/v1/targets | \
  jq -r '.data.activeTargets[] | select(.labels.job | test("calc|risk")) | {job: .labels.job, health: .health, lastError: .lastError}'
```

Все сервисы должны быть `"health": "up"`.

### 2. Проверьте что трафик реально генерируется

```bash
# Счётчик должен расти
watch -n 1 'curl -s http://localhost:7001/metrics | grep "http_requests_total{endpoint=\"/docs\"" | head -1'
```

### 3. Проверьте что Prometheus скрейпит метрики

```bash
# Значение должно совпадать с service metrics (возможна задержка до 15s)
curl -s 'http://localhost:9095/api/v1/query?query=http_requests_total{job="calc-service",endpoint="/docs"}' | \
  jq '.data.result[0].value'
```

### 4. Проверьте Grafana datasource

```bash
curl -s -u admin:admin http://localhost:3030/api/datasources | \
  jq '.[] | select(.name=="Prometheus") | {name, url, uid}'
```

Должно быть: `"url": "http://prometheus:9095"`

---

## 📚 Дополнительные ресурсы

- [prometheus_fastapi_instrumentator docs](https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [Prometheus rate vs irate](https://prometheus.io/docs/prometheus/latest/querying/functions/#rate)
- [Grafana Prometheus datasource](https://grafana.com/docs/grafana/latest/datasources/prometheus/)

---

## ✅ Checklist

- [ ] Трафик генерируется на все сервисы (7001-7011)
- [ ] Метрики `http_requests_total` появились в Prometheus
- [ ] Dashboard queries используют `job` вместо `service`
- [ ] Prometheus rules используют `job` вместо `service`
- [ ] Grafana datasource URL = `prometheus:9095`
- [ ] Grafana dashboard показывает графики (не "No data")
- [ ] Recording rule `api_error_ratio` вычисляется (= 0)
- [ ] Availability panel показывает 100%

---

🎉 **После выполнения всех шагов Stage6 monitoring stack полностью функционален!**
