# ZakupAI custom Vault image with jq preinstalled
FROM hashicorp/vault:1.15

# Устанавливаем jq для парсинга JSON в init-скрипте
RUN apk add --no-cache jq

# Сохраняем стандартную команду по умолчанию
ENTRYPOINT ["/entrypoint.sh"]
CMD ["server"]
