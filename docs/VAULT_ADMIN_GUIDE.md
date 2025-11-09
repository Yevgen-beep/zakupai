# Vault Administrator Guide

Полное руководство по эксплуатации и обслуживанию HashiCorp Vault в проекте ZakupAI.

---

## 📋 Содержание

1. [Ежедневное обслуживание](#ежедневное-обслуживание)
2. [Мониторинг и Alerting](#мониторинг-и-alerting)
3. [Disaster Recovery](#disaster-recovery)
4. [Управление AppRoles](#управление-approles)
5. [Добавление новых сервисов](#добавление-новых-сервисов)
6. [Типовые ошибки и устранение](#типовые-ошибки-и-устранение)
7. [Безопасность](#безопасность)
8. [Ротация секретов](#ротация-секретов)

---

## 1. Ежедневное обслуживание

### Утренние проверки (Daily Health Check)

Рекомендуется выполнять каждое утро:

```bash
# 1. Проверка статуса Vault
make vault-prod-status

# Ожидаемый вывод:
# Sealed: false
# Cluster Name: vault-cluster-...
# Version: 1.15.x

# 2. Проверка метрик Prometheus
curl -s http://localhost:9090/api/v1/query?query=vault_core_unsealed | jq '.data.result[0].value[1]'
# Ожидается: "1"

# 3. Проверка audit log
tail -20 monitoring/vault/logs/audit.log

# 4. Проверка размера audit log
du -h monitoring/vault/logs/audit.log
# Если >100MB, запланировать ротацию

# 5. Проверка последнего backup
ls -lht backups/vault/ | head -5
# Должен быть файл за последние 24 часа
```

### Еженедельные задачи

**Каждый понедельник:**

```bash
# 1. Проверить TLS сертификат (expiry)
openssl x509 -in monitoring/vault/tls/vault-cert.pem -noout -enddate

# 2. Проверить backups в B2
b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"
b2 ls zakupai-vault-storage --recursive | tail -10

# 3. Проверить Prometheus alerts
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name | contains("vault"))'

# 4. Проверить использование ресурсов
docker stats vault --no-stream
```

### Ежемесячные задачи

**Первая неделя месяца:**

```bash
# 1. Disaster Recovery тест (staging)
./scripts/vault-migrate-stage9.sh backup
# Проверить успешность загрузки в B2

# 2. Обновление документации
# Проверить актуальность docs/VAULT_ADMIN_GUIDE.md

# 3. Review audit log для аномалий
# Запустить анализ за последний месяц
grep -i "denied\|failed" monitoring/vault/logs/audit.log | wc -l

# 4. Проверить версию Vault и наличие обновлений
docker exec vault vault version
# Сравнить с https://releases.hashicorp.com/vault/
```

---

## 2. Мониторинг и Alerting

### Prometheus Метрики

#### Ключевые метрики для мониторинга:

| Метрика | Нормальное значение | Действие при отклонении |
|---------|---------------------|-------------------------|
| `vault_core_unsealed` | `1` | Unseal Vault немедленно |
| `up{job="vault"}` | `1` | Проверить контейнер |
| `vault_core_handle_request{quantile="0.99"}` | `<0.1s` | Проверить B2 latency |
| `vault_token_creation_failed` | `<5/min` | Проверить auth issues |
| `vault_storage_backend_unreachable` | `0` | Проверить B2 connectivity |

#### Проверка метрик вручную:

```bash
# Vault unsealed
curl -s http://localhost:8200/v1/sys/metrics?format=prometheus | grep vault_core_unsealed

# Request latency (p99)
curl -s http://localhost:8200/v1/sys/metrics?format=prometheus | grep vault_core_handle_request

# Token creation rate
curl -s http://localhost:8200/v1/sys/metrics?format=prometheus | grep vault_token_creation
```

### Grafana Dashboard

**Основные панели:**

1. **Vault Health**
   - Sealed status
   - Uptime
   - API response time

2. **Performance**
   - Request rate
   - Latency (p50, p95, p99)
   - Error rate

3. **Security**
   - Auth failures
   - Token creation rate
   - Audit log activity

4. **Storage**
   - B2 write latency
   - Storage operations
   - Backup status

**Доступ к dashboard:**
```bash
# Открыть Grafana
open http://localhost:3030
# Username: admin
# Password: admin

# Найти dashboard: "Vault Overview"
```

### Alert Rules

Все alert rules определены в: `monitoring/prometheus/alerts/vault.yml`

**Критичные алерты (требуют немедленного действия):**

- `VaultDown` - Vault недоступен
- `VaultSealed` - Vault запечатан
- `VaultStorageUnreachable` - Нет доступа к B2
- `VaultHighAuthFailures` - Подозрение на атаку

**Warning алерты (требуют внимания в течение часа):**

- `VaultHighLatency` - Высокая задержка
- `VaultHighRequestRate` - Необычно высокий RPS
- `VaultTLSCertExpiringSoon` - Сертификат истекает <30 дней

### Alertmanager Integration

**Настройка уведомлений:**

```yaml
# monitoring/alertmanager/config.yml
route:
  receiver: 'team-vault'
  routes:
    - match:
        severity: critical
        service: vault
      receiver: 'team-vault-critical'

receivers:
  - name: 'team-vault-critical'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK'
        channel: '#vault-alerts'
        title: '🔴 CRITICAL: {{ .GroupLabels.alertname }}'
```

---

## 3. Disaster Recovery

### Backup Strategy

**Автоматический backup:**
- **Частота**: Ежедневно в 2:00 AM
- **Хранилище**: Backblaze B2 bucket `zakupai-vault-storage`
- **Retention**: 30 дней (auto-cleanup)

**Проверка backup:**
```bash
# Список backups в B2
b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"
b2 ls zakupai-vault-storage --recursive

# Ручной backup
./scripts/vault-migrate-stage9.sh backup

# Проверка local backup
ls -lh backups/vault/
```

### Восстановление из Backup

#### Scenario 1: Восстановление данных (B2 доступен)

Vault работает, но данные повреждены:

```bash
# 1. Остановить Vault
docker-compose down vault

# 2. Найти последний backup в B2
b2 ls zakupai-vault-storage --recursive | grep vault-backup | tail -5

# 3. Скачать backup
b2 download-file-by-name zakupai-vault-storage \
    vault-backups/vault-stage8-backup-YYYYMMDD-HHMMSS.tar.gz \
    ./restore-backup.tar.gz

# 4. Распаковать
tar -xzf restore-backup.tar.gz

# 5. Запустить Vault
docker-compose up -d vault

# 6. Проверить
sleep 30
vault status
vault kv list zakupai/
```

#### Scenario 2: Полная катастрофа (новый сервер)

Весь сервер утерян, восстановление с нуля:

```bash
# 1. Клонировать репозиторий
git clone https://github.com/zakupai/zakupai.git
cd zakupai

# 2. Восстановить unseal password из secure storage
# (должен быть сохранён в 1Password/Bitwarden)
echo "YOUR_MASTER_PASSWORD" > monitoring/vault/.unseal-password
chmod 600 monitoring/vault/.unseal-password

# 3. Скачать encrypted unseal key из backup
b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"
b2 download-file-by-name zakupai-vault-storage \
    vault-backups/vault-stage8-backup-YYYYMMDD-HHMMSS.tar.gz \
    ./restore-backup.tar.gz

# 4. Распаковать
tar -xzf restore-backup.tar.gz

# 5. Установить Vault Stage 9
export AWS_ACCESS_KEY_ID="your_b2_key_id"
export AWS_SECRET_ACCESS_KEY="your_b2_app_key"
./setup_vault_evolution.sh --stage9-final --yes

# 6. Проверить
./verify_vault_postdeploy.sh
```

#### Scenario 3: B2 недоступен (failover на file backend)

B2 сервис недоступен, временный переход на file backend:

```bash
# 1. Rollback на Stage 8
make rollback-stage9

# 2. Восстановить данные из local backup
LATEST_BACKUP=$(ls -t backups/vault/vault-stage8-backup-*.tar.gz | head -1)
tar -xzf "$LATEST_BACKUP" -C /

# 3. Запустить Vault
docker-compose up -d vault

# 4. Проверить
vault status

# Когда B2 восстановится:
# 5. Вернуться на Stage 9
./setup_vault_evolution.sh --stage9-final
```

### RTO и RPO

**Целевые показатели:**

| Сценарий | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) |
|----------|-------------------------------|--------------------------------|
| Restart контейнера | <1 минута | 0 (нет потери данных) |
| Восстановление из B2 | <15 минут | <24 часа (последний backup) |
| Полная катастрофа | <2 часа | <24 часа |
| B2 failover | <30 минут | <24 часа |

---

## 4. Управление AppRoles

### Список текущих AppRoles

```bash
# Список всех AppRoles
vault list auth/approle/role

# Ожидаемый вывод:
# calc-service
# etl-service
# risk-engine
# gateway
# alertmanager
```

### Просмотр политики AppRole

```bash
# Получить Role ID
vault read auth/approle/role/gateway/role-id

# Получить Secret ID
vault write -f auth/approle/role/gateway/secret-id

# Просмотреть политики
vault read auth/approle/role/gateway

# Просмотреть содержимое политики
vault policy read gateway-policy
```

### Ротация Secret ID

Рекомендуется каждые 90 дней:

```bash
# 1. Создать новый Secret ID
NEW_SECRET_ID=$(vault write -f -format=json auth/approle/role/gateway/secret-id | jq -r '.data.secret_id')

# 2. Обновить .env в сервисе
echo "VAULT_SECRET_ID=$NEW_SECRET_ID" >> services/gateway/.env.vault

# 3. Перезапустить сервис
docker-compose restart gateway

# 4. Проверить, что сервис работает
curl http://localhost:8080/health

# 5. Удалить старый Secret ID (опционально, если знаем accessor)
vault write auth/approle/role/gateway/secret-id-accessor/destroy \
    secret_id_accessor=<OLD_ACCESSOR>
```

### Проверка прав AppRole

```bash
# Логин с AppRole
VAULT_TOKEN=$(vault write -format=json auth/approle/login \
    role_id="$ROLE_ID" \
    secret_id="$SECRET_ID" | jq -r '.auth.client_token')

# Проверить доступные политики
VAULT_TOKEN=$VAULT_TOKEN vault token lookup | grep policies

# Проверить доступ к секретам
VAULT_TOKEN=$VAULT_TOKEN vault kv get zakupai/gateway/db
```

---

## 5. Добавление новых сервисов

### Полный процесс добавления нового сервиса

**Пример: добавление сервиса `notification-service`**

#### Шаг 1: Создать политику

```bash
# Создать файл политики
cat > notification-service-policy.hcl <<EOF
# Read access to notification service secrets
path "zakupai/notification-service/*" {
  capabilities = ["read", "list"]
}

# Read access to shared secrets
path "zakupai/shared/*" {
  capabilities = ["read", "list"]
}
EOF

# Применить политику
vault policy write notification-service-policy notification-service-policy.hcl
```

#### Шаг 2: Создать AppRole

```bash
# Создать AppRole
vault write auth/approle/role/notification-service \
    token_ttl=1h \
    token_max_ttl=24h \
    secret_id_ttl=0 \
    token_policies="notification-service-policy"

# Получить Role ID
ROLE_ID=$(vault read -format=json auth/approle/role/notification-service/role-id | jq -r '.data.role_id')

# Создать Secret ID
SECRET_ID=$(vault write -f -format=json auth/approle/role/notification-service/secret-id | jq -r '.data.secret_id')

echo "Role ID: $ROLE_ID"
echo "Secret ID: $SECRET_ID"
```

#### Шаг 3: Добавить секреты

```bash
# Добавить конфигурацию БД
vault kv put zakupai/notification-service/db \
    host="postgres" \
    port="5432" \
    database="notifications" \
    username="notif_user" \
    password="$(openssl rand -base64 32)"

# Добавить API ключи
vault kv put zakupai/notification-service/api \
    smtp_host="smtp.gmail.com" \
    smtp_port="587" \
    smtp_username="notifications@zakupai.com" \
    smtp_password="$(openssl rand -base64 24)"

# Добавить Telegram bot
vault kv put zakupai/notification-service/telegram \
    bot_token="YOUR_BOT_TOKEN" \
    chat_id="YOUR_CHAT_ID"
```

#### Шаг 4: Настроить сервис

```bash
# Создать .env.vault для сервиса
cat > services/notification-service/.env.vault <<EOF
VAULT_ADDR=https://vault.zakupai.local:8200
VAULT_ROLE_ID=$ROLE_ID
VAULT_SECRET_ID=$SECRET_ID
VAULT_SKIP_VERIFY=false
EOF

chmod 600 services/notification-service/.env.vault
```

#### Шаг 5: Интегрировать Vault клиент

**Python пример (используя hvac):**

```python
# services/notification-service/vault_client.py
import hvac
import os

class VaultClient:
    def __init__(self):
        self.client = hvac.Client(
            url=os.getenv('VAULT_ADDR'),
            verify=os.getenv('VAULT_SKIP_VERIFY', 'true').lower() != 'true'
        )
        self._authenticate()

    def _authenticate(self):
        role_id = os.getenv('VAULT_ROLE_ID')
        secret_id = os.getenv('VAULT_SECRET_ID')

        self.client.auth.approle.login(
            role_id=role_id,
            secret_id=secret_id,
        )

    def get_secret(self, path):
        """Получить секрет из Vault"""
        response = self.client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point='zakupai'
        )
        return response['data']['data']

# Использование
vault = VaultClient()
db_config = vault.get_secret('notification-service/db')
print(f"DB Host: {db_config['host']}")
```

#### Шаг 6: Тестирование

```bash
# Проверить доступ
vault login -method=approle role_id="$ROLE_ID" secret_id="$SECRET_ID"

# Проверить чтение секретов
vault kv get zakupai/notification-service/db

# Запустить сервис
docker-compose up -d notification-service

# Проверить логи
docker logs notification-service -f
```

---

## 6. Типовые ошибки и устранение

### Ошибка: "Vault is sealed"

**Симптомы:**
```
Error: Vault is sealed
```

**Причина:** Vault запечатан после рестарта, auto-unseal не сработал.

**Решение:**
```bash
# 1. Проверить логи
docker logs vault --tail 50

# 2. Проверить наличие encrypted key
ls -lh monitoring/vault/creds/vault-unseal-key.enc

# 3. Проверить master password
cat monitoring/vault/.unseal-password

# 4. Ручной unseal для диагностики
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# 5. Перезапустить с auto-unseal
docker restart vault
```

---

### Ошибка: "permission denied"

**Симптомы:**
```
Error: permission denied
```

**Причина:** AppRole не имеет прав на запрашиваемый путь.

**Решение:**
```bash
# 1. Проверить политику AppRole
vault read auth/approle/role/gateway

# 2. Проверить содержимое политики
vault policy read gateway-policy

# 3. Проверить, может ли token читать путь
vault token capabilities zakupai/gateway/db

# 4. Обновить политику, если нужно
vault policy write gateway-policy gateway-policy.hcl
```

---

### Ошибка: "connection refused" (B2)

**Симптомы:**
```
Error: failed to write to backend: connection refused
```

**Причина:** Нет доступа к Backblaze B2.

**Решение:**
```bash
# 1. Проверить B2 credentials
docker exec vault env | grep AWS

# 2. Проверить B2 connectivity
curl -I https://s3.us-west-004.backblazeb2.com

# 3. Проверить bucket
b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"
b2 get-bucket zakupai-vault-storage

# 4. Временный failover на file backend
make rollback-stage9

# 5. Когда B2 восстановится
./setup_vault_evolution.sh --stage9-final
```

---

### Ошибка: "TLS certificate expired"

**Симптомы:**
```
Error: x509: certificate has expired
```

**Причина:** TLS сертификат истёк.

**Решение:**
```bash
# 1. Проверить expiry
openssl x509 -in monitoring/vault/tls/vault-cert.pem -noout -enddate

# 2. Генерировать новый сертификат
make vault-tls-renew

# 3. Перезапустить Vault
docker restart vault

# 4. Проверить
curl https://127.0.0.1:8200/v1/sys/health
```

---

## 7. Безопасность

### Security Checklist

- [ ] **Unseal keys зашифрованы** (AES-256 + PBKDF2 ≥250k)
- [ ] **Master password в безопасном хранилище** (1Password/Bitwarden)
- [ ] **Root token никогда не используется** (только emergency)
- [ ] **TLS enabled** в production (Stage 9)
- [ ] **Audit log активен** и ротируется
- [ ] **Файлы с ключами chmod 600**
- [ ] **Backups в B2 encrypted**
- [ ] **Network firewall**: 8200 только из внутренней сети
- [ ] **Prometheus alerts настроены**
- [ ] **Token TTL ограничен** (<24h)
- [ ] **Secret rotation каждые 90 дней**

### Audit Log Analysis

```bash
# Поиск неудачных авторизаций
grep '"type":"response"' monitoring/vault/logs/audit.log | \
    jq 'select(.error != null and .error != "")' | \
    jq -r '[.time, .auth.display_name, .error] | @tsv'

# Топ 10 пользователей по количеству запросов
grep '"type":"request"' monitoring/vault/logs/audit.log | \
    jq -r '.auth.display_name' | sort | uniq -c | sort -rn | head -10

# Поиск аномальных операций (удаление)
grep '"operation":"delete"' monitoring/vault/logs/audit.log | \
    jq -r '[.time, .auth.display_name, .request.path] | @tsv'
```

---

## 8. Ротация секретов

### Ротация database credentials

```bash
# 1. Генерация нового пароля
NEW_PASSWORD=$(openssl rand -base64 32)

# 2. Обновление в PostgreSQL
psql -U postgres -c "ALTER USER gateway_user PASSWORD '$NEW_PASSWORD';"

# 3. Обновление в Vault
vault kv put zakupai/gateway/db \
    host="postgres" \
    port="5432" \
    database="zakupai" \
    username="gateway_user" \
    password="$NEW_PASSWORD"

# 4. Перезапуск сервиса
docker-compose restart gateway

# 5. Проверка
curl http://localhost:8080/health
```

### Ротация TLS сертификатов

```bash
# Автоматическая ротация (cron)
0 0 1 * * cd /path/to/zakupai && make vault-tls-renew && docker restart vault

# Ручная ротация
make vault-tls-renew
docker restart vault
```

---

**Автор:** ZakupAI DevOps Team
**Версия:** 1.0
**Дата:** 2025-11-07
