# Stage 7 — Phase 2: Vault Integration + Secrets Management

**Дата начала:** 2025-10-27  
**Ветка:** `feature/stage7-phase2-vault-auth`  
**Фаза:** 2 из 3  
**Статус:** 🟡 В процессе планирования  

---

## 🌟 Цель фазы

🔒 Перейти от базовой защиты (валидация, rate limit, payload limit)  к полноценной **интеграции Vault + Secrets Management**:

- Централизованное хранение секретов (Vault 1.17)
- Безопасная загрузка конфиденциальных данных через hvac
- Удаление `.env` из Docker-сборок
- Настройка реальных уведомлений Alertmanager → Telegram
- Добавление бизнес-метрик (anti-dumping, goszakup errors)

---

## 🔧 Этапы выполнения

### 🔹 День 1: Развёртывание Vault

**Цель:** поднять Vault как контейнер и инициализировать root token.

**Действия:**
1. Добавить в `docker-compose.override.monitoring.yml`:
   ```yaml
   vault:
     image: hashicorp/vault:1.17
     container_name: zakupai-vault
     ports:
       - "8200:8200"
     environment:
       - VAULT_ADDR=http://0.0.0.0:8200
     volumes:
       - ./monitoring/vault:/vault/file
       - ./monitoring/vault/config.hcl:/vault/config/config.hcl
     command: server -config=/vault/config/config.hcl
   ```
2. Создать `monitoring/vault/config.hcl`:
   ```hcl
   storage "file" {
     path = "/vault/file"
   }

   listener "tcp" {
     address     = "0.0.0.0:8200"
     tls_disable = 1
   }

   disable_mlock = true
   ui = true
   ```
3. Инициализация:
   ```bash
   docker exec -it zakupai-vault vault operator init
   docker exec -it zakupai-vault vault login <root_token>
   vault secrets enable -path=zakupai kv
   ```

---

### 🔹 День 2–3: Интеграция hvac в сервисы

**Цель:** перенести чтение секретов из `.env` в Vault.

1. Обновить `libs/zakupai_common/vault_client.py`:
   ```python
   import hvac, os

   class VaultClientError(Exception): ...

   def get_client():
       addr = os.getenv("VAULT_ADDR", "http://vault:8200")
       token = os.getenv("VAULT_TOKEN")
       return hvac.Client(url=addr, token=token)

   def load_kv_to_env(path="zakupai/data/secrets"):
       client = get_client()
       data = client.secrets.kv.v2.read_secret_version(path=path)
       for k, v in data["data"]["data"].items():
           os.environ[k] = v
   ```
2. В `main.py` каждого сервиса (calc, etl, risk):
   ```python
   from zakupai_common.vault_client import load_kv_to_env

   try:
       load_kv_to_env("zakupai/data/<service>")
   except Exception as e:
       print(f"Vault load failed: {e}")
   ```
3. Удалить `.env` из Dockerfile:
   ```dockerfile
   # before:
   COPY .env .
   # remove this line
   ```

---

### 🔹 День 4: Alertmanager Webhook (Telegram/Slack)

**Цель:** включить реальные уведомления.

1. Добавить в `monitoring/alertmanager/alertmanager.yml`:
   ```yaml
   route:
     receiver: "telegram"

   receivers:
     - name: "telegram"
       telegram_configs:
         - bot_token: ${TELEGRAM_BOT_TOKEN}
           chat_id: ${TELEGRAM_CHAT_ID}
           message: |
             🚨 *{{ .CommonLabels.alertname }}*
             Instance: {{ .CommonLabels.instance }}
             {{ .Annotations.description }}
   ```
2. Сохранить секреты в Vault:
   ```bash
   vault kv put zakupai/data/monitoring TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
   ```

---

### 🔹 День 5: Business Metrics + Grafana

**Цель:** добавить anti-dumping % и goszakup errors.

1. В `risk-engine/metrics.py`:
   ```python
   from prometheus_client import Gauge, Counter

   anti_dumping_ratio = Gauge("anti_dumping_ratio", "Anti-dumping violations per 100 lots")
   goszakup_errors_total = Counter("goszakup_errors_total", "Errors from Goszakup API")
   ```
2. В `main.py`:
   ```python
   from prometheus_client import start_http_server
   start_http_server(9102)
   ```
3. Импортировать дашборд `grafana/business_metrics.json`.

---

## 🔬 DoD (Definition of Done)

| Критерий | Состояние |
|-----------|------------|
| Vault контейнер активен | ✅ `curl http://localhost:8200/v1/sys/health` → initialized=true |
| calc/etl/risk запускаются без .env | ✅ Vault secrets loaded |
| hvac клиент работает | ✅ vault status → connected |
| Alertmanager шлёт уведомления | ✅ Telegram / Slack message received |
| Grafana business metrics | ✅ Dashboard visible |
| Prometheus scrape | ✅ /metrics содержит anti_dumping_ratio |

---

## 🚀 План после завершения Phase 2

🔒 **Stage 7 Phase 3 — Auth Middleware + API Keys:**
- JWT интеграция
- API-Key аутентификация через billing-service
- Redis-backed Rate Limiter
- Gateway Auth Proxy для /api/

---

**Дата готовности:** 2025-11-03  
**Ответственный:** ZakupAI DevOps Team  
**Отчёт:** STAGE7_PHASE2_RESULTS.md
