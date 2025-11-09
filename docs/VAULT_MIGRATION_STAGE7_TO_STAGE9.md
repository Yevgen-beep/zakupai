# Vault Migration: Stage 7 → Stage 9

## 🎯 Цели и принципы миграции

### Цели
- **Stage 7 → Stage 8**: Внедрить автоматический unseal с AES-256 шифрованием
- **Stage 8 → Stage 9**: Перейти на production-ready архитектуру с B2 storage, TLS и audit logging
- Обеспечить zero-downtime миграцию для секретов AppRole
- Автоматизировать backup и recovery процессы

### Принципы
- **Безопасность**: AES-256 + PBKDF2 ≥250k итераций, TLS в production
- **Надёжность**: Автоматический unseal, HA-ready storage (B2)
- **Наблюдаемость**: Audit logs, Prometheus metrics, health checks
- **Reversibility**: Полный rollback план для каждой стадии
- **Immutability**: Все конфигурации в Git (кроме ключей)

---

## 📊 Таблица стадий

| Параметр | Stage 7 (Manual) | Stage 8 (Auto-Unseal File) | Stage 9 (Production B2) |
|----------|------------------|----------------------------|-------------------------|
| **Storage** | File (local) | File (local) | S3 (Backblaze B2) |
| **Unseal** | Manual (3/5 keys) | Auto (AES-256 encrypted) | Auto (AES-256 encrypted) |
| **TLS** | Disabled | Disabled | Enabled (Let's Encrypt) |
| **Audit** | Disabled | Disabled | Enabled (file + rotation) |
| **UI** | Enabled | Enabled | Enabled (over TLS) |
| **Mlock** | Disabled (Docker) | Disabled (Docker) | Disabled (Docker) |
| **Healthcheck** | Basic | Sealed=false | Sealed=false + TLS |
| **Backup** | Manual | Daily (local) | Daily (B2 bucket) |
| **HA** | No | No | Ready (S3-based) |
| **Production** | ❌ Dev only | ⚠️ Staging | ✅ Production |

---

## 🗺️ Roadmap миграции

### Phase 1: Stage 7 → Stage 8 (Auto-Unseal on File Backend)

| Шаг | Описание | Команда | Время |
|-----|----------|---------|-------|
| 1.1 | Создать backup текущего Vault | `make vault-secure-backup` | 1 мин |
| 1.2 | Сгенерировать master password для шифрования | `openssl rand -base64 32 > .unseal-password` | 1 мин |
| 1.3 | Зашифровать unseal ключи | `./monitoring/vault/scripts/encrypt-unseal.sh` | 2 мин |
| 1.4 | Применить Stage 8 конфигурацию | `make stage8` | 3 мин |
| 1.5 | Проверить auto-unseal после рестарта | `docker restart vault && sleep 5 && make vault-secure-status` | 2 мин |
| 1.6 | Проверить доступ к секретам AppRole | `make vault-secure-test` | 1 мин |
| **Total** | | | **~10 мин** |

### Phase 2: Stage 8 → Stage 9 (Production B2 + TLS + Audit)

| Шаг | Описание | Команда | Время |
|-----|----------|---------|-------|
| 2.1 | Создать snapshot Vault data | `make vault-secure-backup` | 2 мин |
| 2.2 | Настроить Backblaze B2 credentials | `export B2_APPLICATION_KEY_ID=...` | 1 мин |
| 2.3 | Создать B2 bucket для Vault | `b2 create-bucket zakupai-vault-storage allPrivate` | 1 мин |
| 2.4 | Генерация TLS сертификатов | `make vault-tls-renew` | 5 мин |
| 2.5 | Миграция storage в B2 | `./scripts/vault-migrate-stage9.sh` | 10 мин |
| 2.6 | Применить Stage 9 конфигурацию | `make stage9` | 3 мин |
| 2.7 | Проверить TLS и audit logs | `make smoke-stage9` | 2 мин |
| 2.8 | Настроить cron для backups | `crontab -e` (добавить задачу) | 2 мин |
| **Total** | | | **~26 мин** |

---

## 🔄 Rollback план

### Rollback Stage 8 → Stage 7

```bash
# 1. Остановить Vault
docker-compose down vault

# 2. Восстановить Stage 7 конфигурацию
cp monitoring/vault/config/stage7-config.hcl monitoring/vault/config/vault-config.hcl

# 3. Удалить Stage 8 override
rm -f docker-compose.override.yml

# 4. Запустить Vault
docker-compose up -d vault

# 5. Ручной unseal
export VAULT_ADDR='http://127.0.0.1:8200'
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# 6. Проверка
vault status
vault kv list zakupai/
```

**Время**: ~5 минут
**Потеря данных**: Нет (если backup актуален)

### Rollback Stage 9 → Stage 8

```bash
# 1. Создать emergency snapshot из B2
make vault-prod-backup

# 2. Остановить Vault
docker-compose down vault

# 3. Восстановить Stage 8 конфигурацию
cp monitoring/vault/config/secure/config.hcl monitoring/vault/config/vault-config.hcl
cp docker-compose.override.stage8.vault-secure.yml docker-compose.override.yml

# 4. Восстановить data из snapshot
tar -xzf vault-backup-*.tar.gz -C monitoring/vault/data/

# 5. Запустить Vault (auto-unseal)
docker-compose up -d vault

# 6. Проверка
sleep 10
vault status
vault kv list zakupai/
```

**Время**: ~10 минут
**Потеря данных**: Данные с момента последнего backup

---

## 🛡️ Security Checklist

### Pre-Migration
- [ ] Backup всех unseal ключей в безопасное место (1Password/Bitwarden)
- [ ] Root token сохранён в encrypted хранилище
- [ ] `.unseal-password` создан и НЕ в Git
- [ ] Права на `monitoring/vault/creds/*` установлены в `600`
- [ ] `vault-unseal-key.enc` добавлен в `.gitignore`

### Stage 8 Security
- [ ] AES-256 encryption применён для unseal ключей
- [ ] PBKDF2 использует ≥250,000 итераций
- [ ] Master password ≥32 символа (или 24 байта base64)
- [ ] Auto-unseal работает без plain-text ключей
- [ ] Restart не требует ручного unseal

### Stage 9 Security
- [ ] TLS сертификат валиден и автообновляется
- [ ] B2 Application Keys с минимальными правами (только bucket)
- [ ] Audit log включён и пишется в rotated файл
- [ ] `tls_disable = false` в конфигурации
- [ ] `VAULT_SKIP_VERIFY=false` в окружении сервисов
- [ ] Firewall правила: 8200 только из внутренней сети
- [ ] Prometheus alerts настроены (VaultSealed, VaultDown)

### Post-Migration
- [ ] Все AppRole policies работают корректно
- [ ] Secrets доступны из сервисов (gateway, risk-engine, billing)
- [ ] Backups автоматически заливаются в B2 (cron)
- [ ] Monitoring dashboard показывает Sealed=false
- [ ] Latency < 100ms (99th percentile)
- [ ] Audit logs пишутся и ротируются

---

## 📈 SLA-метрики

### Availability
| Метрика | Цель | Мониторинг |
|---------|------|------------|
| Vault Sealed | `false` | `vault_core_unsealed == 1` |
| Uptime | >99.5% | `up{job="vault"} == 1` |
| Auto-Unseal Time | <30s | Healthcheck timeout |

### Performance
| Метрика | Цель | Мониторинг |
|---------|------|------------|
| Request Latency (p99) | <100ms | `vault_core_handle_request` |
| Token Creation | <50ms | `vault_token_creation` |
| Secret Read | <20ms | `vault_kv_read_duration` |

### Reliability
| Метрика | Цель | Мониторинг |
|---------|------|------------|
| Backup Success Rate | 100% | Cron job exit code |
| Backup Freshness | <24h | `ls -lh vault-backup-*.tar.gz` |
| B2 Upload Success | >99% | `b2 get-bucket zakupai-vault-storage` |

### Security
| Метрика | Цель | Мониторинг |
|---------|------|------------|
| Audit Log Entries | >0/min (prod) | `wc -l audit.log` |
| TLS Certificate Expiry | >30 days | `openssl x509 -enddate` |
| Failed Auth Attempts | <10/hour | Audit log grep |

---

## 🚀 Quick Start

### Stage 8 Migration (Auto-Unseal)
```bash
# 1. Генерация master password
openssl rand -base64 32 > monitoring/vault/.unseal-password
chmod 600 monitoring/vault/.unseal-password

# 2. Запуск миграции
./scripts/vault-migrate-stage8.sh

# 3. Проверка
docker restart vault
sleep 10
make vault-secure-status  # Должен быть unsealed
```

### Stage 9 Migration (Production B2)
```bash
# 1. Настройка B2 credentials
export B2_APPLICATION_KEY_ID="ваш_key_id"
export B2_APPLICATION_KEY="ваш_application_key"

# 2. Создание bucket
b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"
b2 create-bucket zakupai-vault-storage allPrivate

# 3. Генерация TLS
make vault-tls-renew

# 4. Запуск миграции
./scripts/vault-migrate-stage9.sh

# 5. Проверка
make smoke-stage9  # Все тесты должны пройти
```

---

## 📞 Troubleshooting

### Vault остаётся sealed после рестарта (Stage 8)

**Симптомы**: `vault status` показывает `Sealed: true`

**Диагностика**:
```bash
docker logs vault --tail 50
cat monitoring/vault/logs/vault.log
```

**Решение**:
```bash
# Проверить наличие зашифрованного ключа
ls -lh monitoring/vault/creds/vault-unseal-key.enc

# Проверить master password
cat monitoring/vault/.unseal-password

# Перезапустить с ручным unseal для теста
docker-compose down vault
docker-compose up -d vault
vault operator unseal <ключ_из_init>
```

### B2 upload fails (Stage 9)

**Симптомы**: `b2 upload-file` возвращает 401 Unauthorized

**Решение**:
```bash
# Перезалогиниться в B2
b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"

# Проверить bucket
b2 list-buckets

# Проверить Application Key права (должен быть readFiles + writeFiles)
```

### TLS certificate invalid

**Симптомы**: `curl: (60) SSL certificate problem: self signed certificate`

**Решение**:
```bash
# Проверить сертификат
openssl x509 -in monitoring/vault/tls/vault-cert.pem -text -noout

# Перегенерировать
make vault-tls-renew

# Для разработки (ТОЛЬКО DEV):
export VAULT_SKIP_VERIFY=true
```

---

## 📚 Ссылки

- [Vault Auto-Unseal Documentation](https://developer.hashicorp.com/vault/docs/concepts/seal)
- [Backblaze B2 S3 Compatible API](https://www.backblaze.com/b2/docs/s3_compatible_api.html)
- [Vault Audit Devices](https://developer.hashicorp.com/vault/docs/audit)
- [Vault Health Endpoints](https://developer.hashicorp.com/vault/api-docs/system/health)

---

## ✅ Definition of Done (DoD)

### Stage 8
- [x] Vault auto-unseal работает после `docker restart vault`
- [x] Unseal ключи зашифрованы AES-256 + PBKDF2 ≥250k
- [x] Plain-text ключи удалены из Git
- [x] `.unseal-password` в `.gitignore`
- [x] Healthcheck проверяет `Sealed=false`
- [x] Все AppRole работают без изменений

### Stage 9
- [x] B2 storage подключён и активен
- [x] TLS сертификат валиден (openssl verify)
- [x] Audit log создаётся в `monitoring/vault/logs/audit.log`
- [x] Backup автоматически заливается в B2 (cron job)
- [x] Prometheus alerts: `VaultSealed`, `VaultDown`
- [x] `make smoke-stage9` проходит все тесты
- [x] Latency <100ms (p99)

---

**Версия документа**: 1.0
**Дата**: 2025-11-07
**Автор**: ZakupAI DevOps Team
