# ZakupAI custom Vault image with jq preinstalled
FROM hashicorp/vault:1.17

# Устанавливаем jq для парсинга JSON в init-скрипте
RUN apk add --no-cache jq curl bash

# Сохраняем стандартную команду и entrypoint из базового образа
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["server"]
