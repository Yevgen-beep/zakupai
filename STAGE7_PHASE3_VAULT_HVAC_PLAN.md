STAGE 7 — Phase 3: Vault hvac Integration & Secrets Management

Цель:
Полная миграция секретов из .env в HashiCorp Vault + автоматическая загрузка через hvac
для сервисов calc-service, etl-service и risk-engine.

Этапы реализации
I. Vault Initialization
Создать init-vault.sh
[ ] vault operator init → сохранить creds/init.json
[ ] vault operator unseal → применить 3 ключа
[ ] Сгенерировать CA и настроить /v1/pki/ca
[ ] Добавить KV engine: vault secrets enable -path=zakupai kv-v2
[ ] Создать политику zakupai-policy.hcl
[ ] Включить AppRole и создать роли:
    etl-service
    calc-service
    risk-engine

II. hvac Integration
[ ] Добавить hvac в requirements.txt (все три сервиса)
[ ] Создать /libs/vault_client.py
[ ] В каждом main.py добавить load_secrets() перед запуском приложения
[ ] Передавать VAULT_ADDR, VAULT_ROLE_ID, VAULT_SECRET_ID из compose
[ ] Проверить чтение секретов из KV zakupai/app

III. Compose & CI/CD
[ ] Удалить .env из Docker-сборок
[ ] Добавить vault status healthcheck
[ ] Добавить healthcheck для ETL (curl /health)
[ ] Обновить .github/workflows:
[ ] vault login → vault kv get zakupai/app

IV. Pydantic & Bootstrap
[ ] Исправить schema_extra → model_config
[ ] Добавить временный VAULT_TOKEN=dummy-local-token для bootstrap

V. DoD — Definition of Done
[ ] Все сервисы стартуют без .env
[ ] hvac получает секреты из Vault KV
[ ] Alertmanager использует токен из Vault
[ ] Все healthchecks → Status: healthy
[ ] PR принят и помечен как stable-stage7-phase3

Контрольные команды:
# Проверка Vault
docker exec -it zakupai-vault vault status
docker exec -it zakupai-vault vault kv list zakupai/

# Проверка сервисов
curl http://localhost:7011/health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Базовая структура:
monitoring/vault/
 ├── config.hcl
 ├── creds/init.json
 ├── policies/zakupai-policy.hcl
 ├── init-vault.sh
 └── README.md
libs/
 └── vault_client.py

Phase 3 Summary:

| Компонент       | Задача                   | Статус |
| --------------- | ------------------------ | ------ |
| Vault init      | Создать root-token и CA  | 🚧     |
| hvac интеграция | calc, etl, risk-engine   | 🚧     |
| .env cleanup    | перенос секретов в Vault | 🚧     |
| Alertmanager    | токены из Vault KV       | 🚧     |
| Healthchecks    | Vault + ETL              | ⚙️     |
| Pydantic fix    | model_config             | ⚙️     |
