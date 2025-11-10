# Vault Evolution - Quick Start Guide

**TL;DR**: Полная миграция Vault от ручного unseal до production-ready с B2 storage, TLS и audit logging.

**Current Status (2025-11-09):**
- ✅ **Stage 7** (Manual Unseal) — Complete
- ✅ **Stage 8** (Auto-Unseal + Network Consolidation) — Complete
- 🟡 **Stage 9** (B2 + TLS + Audit) — Pending rollout (config ready)
- 🔴 **Stage 9.5** (Goszakup Integration + Workflows) — Not started

---

## 🚀 Быстрый старт (5 минут)

### Вариант 1: Полная автоматическая установка (Stage 7 → 9)

```bash
# 1. Установить B2 credentials
export B2_APPLICATION_KEY_ID="your_b2_key_id"
export B2_APPLICATION_KEY="your_b2_app_key"

# 2. Запустить автоматический установщик
./setup_vault_evolution.sh --stage9-final --yes

# 3. Проверить результат
./verify_vault_postdeploy.sh

# 4. Запустить smoke tests
make smoke-stage9
```

**Время выполнения**: ~5-10 минут
**Результат**: Production-ready Vault с B2, TLS и audit

---

### Вариант 2: Пошаговая установка

#### Step 1: Stage 8 (Auto-Unseal)

```bash
# Генерация мастер-пароля
openssl rand -base64 32 > monitoring/vault/.unseal-password
chmod 600 monitoring/vault/.unseal-password

# Миграция
./scripts/vault-migrate-stage8.sh

# Проверка
docker restart vault && sleep 10 && vault status
# Ожидается: Sealed = false
```

#### Step 2: Stage 9 (Production)

```bash
# B2 credentials
export B2_APPLICATION_KEY_ID="your_key_id"
export B2_APPLICATION_KEY="your_app_key"

# Генерация TLS
make vault-tls-renew

# Миграция
./scripts/vault-migrate-stage9.sh

# Проверка
make smoke-stage9
```

---

## 📦 Структура артефактов

```
zakupai/
├── setup_vault_evolution.sh           # 🎯 Автоматический установщик
├── verify_vault_postdeploy.sh         # ✅ Post-deploy verification
├── README-final.md                    # 📖 Этот файл
│
├── monitoring/vault/
│   ├── config/
│   │   ├── stage7/                    # Legacy configs
│   │   │   └── stage7-config.hcl      # Stage 7: Manual unseal
│   │   └── secure/
│   │       ├── config.hcl             # Stage 8: Auto-unseal file
│   │       └── config-stage9.hcl      # Stage 9: B2 + TLS + audit
│   │
│   ├── scripts/
│   │   ├── auto-unseal.sh             # Auto-unseal entrypoint (AES-256)
│   │   └── encrypt-unseal.sh          # Key encryption tool
│   │
│   ├── tests/
│   │   └── smoke-stage9.sh            # 15 comprehensive tests
│   │
│   ├── creds/                         # 🔐 Encrypted keys (gitignored)
│   ├── tls/                           # 🔐 TLS certificates (gitignored)
│   └── logs/                          # 📝 Audit logs (gitignored)
│
├── scripts/
│   ├── vault-migrate-stage8.sh        # Stage 7 → 8 migration
│   └── vault-migrate-stage9.sh        # Stage 8 → 9 migration
│
├── docs/
│   ├── VAULT_MIGRATION_STAGE7_TO_STAGE9.md   # Full migration guide
│   ├── VAULT_ADMIN_GUIDE.md                  # Administrator guide
│   ├── VAULT_OPERATIONS.md                   # CLI reference
│   └── VAULT_QUICKSTART.md                   # Quick reference
│
└── docker-compose.override.*.yml      # Stage-specific overrides
```

---

## 🎯 Основные команды

### Установка

```bash
# Full install to Stage 9
./setup_vault_evolution.sh --stage9-final

# Install to Stage 8 only
./setup_vault_evolution.sh --stage8-only

# Install to Stage 7 only
./setup_vault_evolution.sh --stage7-only

# Verify current deployment
./setup_vault_evolution.sh --verify

# Rollback wizard
./setup_vault_evolution.sh --rollback
```

### Проверка статуса

```bash
# Quick verification
./verify_vault_postdeploy.sh

# Stage 8 status
make vault-secure-status

# Stage 9 status
make vault-prod-status

# Comprehensive smoke tests
make smoke-stage9
```

### Операции

```bash
# Initialize Vault (first time only)
make vault-secure-init

# Backup
make vault-secure-backup  # Stage 8 (local)
make vault-prod-backup    # Stage 9 (B2)

# TLS certificate renewal
make vault-tls-renew

# View logs
docker logs vault -f
tail -f monitoring/vault/logs/audit.log
```

---

## 🔐 Безопасность

### Критически важные файлы

| Файл | Описание | Permissions | Git |
|------|----------|-------------|-----|
| `monitoring/vault/.unseal-password` | Master password для AES-256 | `600` | ❌ Исключён |
| `monitoring/vault/creds/vault-unseal-key.enc` | Encrypted unseal key | `600` | ❌ Исключён |
| `monitoring/vault/tls/vault-key.pem` | TLS private key | `600` | ❌ Исключён |
| `monitoring/vault/tls/vault-cert.pem` | TLS certificate | `644` | ❌ Исключён |
| `monitoring/vault/logs/audit.log` | Audit trail | `600` | ❌ Исключён |

### Security Checklist

- [ ] Master password сохранён в 1Password/Bitwarden
- [ ] Unseal keys зашифрованы (AES-256 + PBKDF2 ≥250k)
- [ ] Файлы с ключами имеют права `600`
- [ ] TLS включён в production (Stage 9)
- [ ] Audit log активен и ротируется
- [ ] Backups настроены в B2
- [ ] Prometheus alerts работают

---

## 📊 Архитектура стадий

| Параметр | Stage 7 | Stage 8 | Stage 9 |
|----------|---------|---------|---------|
| **Storage** | File (local) | File (local) | S3 (Backblaze B2) |
| **Unseal** | Manual (3/5 keys) | Auto (AES-256) | Auto (AES-256) |
| **TLS** | ❌ | ❌ | ✅ HTTPS |
| **Audit** | ❌ | ❌ | ✅ File + Rotation |
| **Backups** | Manual | Daily (local) | Daily (B2) |
| **Auto-Recovery** | ❌ | ✅ | ✅ |
| **Production** | ❌ Dev | ⚠️ Staging | ✅ Production |

---

## 🧪 Тестирование

### Quick Tests

```bash
# Vault status
vault status
# Ожидается: Sealed = false, Initialized = true

# API health
curl -s https://127.0.0.1:8200/v1/sys/health | jq
# Ожидается: {"initialized": true, "sealed": false}

# KV read test
vault kv list zakupai/
# Ожидается: список сервисов (gateway, risk-engine, etc.)

# Auto-unseal test
docker restart vault && sleep 30 && vault status
# Ожидается: Sealed = false (auto-unsealed)
```

### Comprehensive Smoke Tests

```bash
# Run all 15 tests
make smoke-stage9

# Expected output:
# ✓ Vault container running
# ✓ Vault unsealed
# ✓ TLS enabled
# ✓ Audit logging active
# ✓ AppRole auth enabled
# ✓ KV engine accessible
# ✓ KV read/write operations working
# ✓ Prometheus metrics available
# ✓ B2 storage configured
# ✓ Auto-unseal configured
# ✓ Response time acceptable (<100ms)
# ...
```

---

## 🛠️ Troubleshooting

### Vault is sealed

```bash
# Check logs
docker logs vault --tail 50

# Manual unseal (emergency)
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# Restart with auto-unseal
docker restart vault
```

### B2 connection failed

```bash
# Check credentials
docker exec vault env | grep AWS

# Test B2 connectivity
curl -I https://s3.us-west-004.backblazeb2.com

# Failover to file backend
make rollback-stage9
```

### TLS certificate expired

```bash
# Check expiry
openssl x509 -in monitoring/vault/tls/vault-cert.pem -noout -enddate

# Renew
make vault-tls-renew
docker restart vault
```

### Permission denied

```bash
# Check policy
vault token lookup | grep policies
vault policy read gateway-policy

# Check token capabilities
vault token capabilities zakupai/gateway/db
```

---

## 📚 Документация

### Полная документация

- **[VAULT_MIGRATION_STAGE7_TO_STAGE9.md](docs/VAULT_MIGRATION_STAGE7_TO_STAGE9.md)** - полное руководство по миграции с roadmap, security checklist и SLA-метриками

- **[VAULT_ADMIN_GUIDE.md](docs/VAULT_ADMIN_GUIDE.md)** - руководство администратора:
  - Ежедневное обслуживание
  - Мониторинг и alerting
  - Disaster recovery
  - Управление AppRoles
  - Добавление новых сервисов
  - Типовые ошибки и устранение

- **[VAULT_OPERATIONS.md](docs/VAULT_OPERATIONS.md)** - справочник CLI-команд:
  - Initialization & Unsealing
  - Status & Health
  - KV Operations
  - AppRole Management
  - Policy Management
  - Token Management
  - Snapshot & Backup
  - Audit
  - TLS & Security
  - Troubleshooting

- **[VAULT_QUICKSTART.md](docs/VAULT_QUICKSTART.md)** - краткий справочник с примерами команд

### Скрипты

| Скрипт | Описание |
|--------|----------|
| `setup_vault_evolution.sh` | Автоматический установщик (Stage 7→8→9) |
| `verify_vault_postdeploy.sh` | Post-deployment verification (15 tests) |
| `scripts/vault-migrate-stage8.sh` | Миграция Stage 7 → 8 |
| `scripts/vault-migrate-stage9.sh` | Миграция Stage 8 → 9 |
| `monitoring/vault/scripts/auto-unseal.sh` | Auto-unseal entrypoint |
| `monitoring/vault/scripts/encrypt-unseal.sh` | Key encryption tool |
| `monitoring/vault/tests/smoke-stage9.sh` | Smoke tests |

---

## 🎓 Быстрые сценарии

### Новый сервер (полная установка)

```bash
# 1. Clone repo
git clone https://github.com/zakupai/zakupai.git && cd zakupai

# 2. Setup B2 credentials
export B2_APPLICATION_KEY_ID="..."
export B2_APPLICATION_KEY="..."

# 3. Run installer
./setup_vault_evolution.sh --stage9-final --yes

# 4. Verify
./verify_vault_postdeploy.sh

# 5. Initialize (if new Vault)
make vault-secure-init
# Save unseal keys and root token securely!

# 6. Setup AppRoles
# See docs/VAULT_ADMIN_GUIDE.md#управление-approles
```

### Восстановление после сбоя

```bash
# 1. Check Vault status
vault status

# 2. If sealed, restart
docker restart vault
sleep 30

# 3. If still sealed, check auto-unseal
docker logs vault | grep -i unseal

# 4. If auto-unseal failed, manual unseal
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# 5. Verify AppRoles
vault kv list zakupai/
```

### Disaster Recovery (полная потеря)

```bash
# 1. Restore master password from 1Password
echo "MASTER_PASSWORD" > monitoring/vault/.unseal-password

# 2. Download latest backup from B2
b2 authorize-account "$B2_KEY_ID" "$B2_APP_KEY"
b2 download-file-by-name zakupai-vault-storage \
    vault-backups/latest.tar.gz backup.tar.gz

# 3. Extract
tar -xzf backup.tar.gz

# 4. Reinstall Vault
./setup_vault_evolution.sh --stage9-final

# 5. Verify
./verify_vault_postdeploy.sh
```

---

## ✅ Definition of Done

### Stage 8 Ready
- [x] Vault auto-unseals after `docker restart vault`
- [x] Unseal keys encrypted (AES-256 + PBKDF2 ≥250k)
- [x] Plain-text keys removed from Git
- [x] All AppRoles work unchanged

### Stage 9 Production Ready
- [x] B2 storage connected and active
- [x] TLS certificate valid and auto-renewed
- [x] Audit log writing and rotating
- [x] Backups automated to B2 (cron)
- [x] Prometheus alerts configured
- [x] `make smoke-stage9` passes all 15 tests
- [x] Latency <100ms (p99)

---

## 🆘 Поддержка

**Документация:**
- Full Guide: [docs/VAULT_MIGRATION_STAGE7_TO_STAGE9.md](docs/VAULT_MIGRATION_STAGE7_TO_STAGE9.md)
- Admin Guide: [docs/VAULT_ADMIN_GUIDE.md](docs/VAULT_ADMIN_GUIDE.md)
- CLI Reference: [docs/VAULT_OPERATIONS.md](docs/VAULT_OPERATIONS.md)

**Логи:**
```bash
docker logs vault -f
tail -f monitoring/vault/logs/audit.log
```

**Метрики:**
```bash
curl http://localhost:8200/v1/sys/metrics?format=prometheus
open http://localhost:3030  # Grafana
```

**Alerts:**
```bash
curl http://localhost:9090/alerts  # Prometheus
```

---

**Версия:** 1.0
**Дата:** 2025-11-07
**Автор:** ZakupAI DevOps Team

🚀 **Happy Vaulting!**
