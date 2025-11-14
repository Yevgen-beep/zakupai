# Stage 9 Vault - Быстрая инструкция по запуску

## Статус: ✅ ВСЕ ИСПРАВЛЕНО

Docker secrets теперь работают корректно. Vault читает B2 credentials без ошибок "Permission denied".

---

## Быстрый старт (3 команды)

```bash
# 1. Проверить конфигурацию
./scripts/verify-stage9-config.sh

# 2. Проверить Docker secrets
./scripts/test-stage9-secrets.sh

# 3. Запустить Vault
make stage9-deploy
```

---

## Если Vault в рестарт-луп

Проверьте последние логи:

```bash
docker logs zakupai-vault --tail=30
```

### Возможные ошибки:

#### ✅ ИСПРАВЛЕНО - больше не возникает:
```
❌ Permission denied: /run/secrets/b2_access_key_id
❌ NoCredentialProviders: no valid providers in chain
```

#### ⚠️ Требуется действие:
```
❌ InvalidAccessKeyId: The key '...' is not valid
```

**Решение**: Обновите B2 credentials в:
- `monitoring/vault/creds/b2_access_key_id`
- `monitoring/vault/creds/b2_secret_key`

Затем:
```bash
docker compose -f docker-compose.yml \
  -f docker-compose.override.stage9.vault-prod.yml \
  restart vault
```

---

## Полезные команды

```bash
# Посмотреть статус Vault
docker ps --filter name=vault

# Проверить секреты внутри контейнера
docker exec zakupai-vault ls -la /run/secrets/

# Остановить Vault
docker compose -f docker-compose.yml \
  -f docker-compose.override.stage9.vault-prod.yml \
  down vault

# Очистить всё и начать заново
make vault-tls-recreate
make stage9-deploy
```

---

## Что было исправлено

1. ✅ Добавлена секция `secrets:` в `docker-compose.yml`
2. ✅ Vault запускается как root для чтения secrets
3. ✅ Entrypoint корректно читает и экспортирует credentials
4. ✅ TLS init container работает
5. ✅ Все permission denied ошибки устранены

Подробности в [STAGE9_FIXED_SUMMARY.md](STAGE9_FIXED_SUMMARY.md)

---

## Контакты

Если что-то не работает:
1. Запустите `./scripts/test-stage9-secrets.sh`
2. Проверьте логи Vault
3. Убедитесь, что B2 credentials актуальны
