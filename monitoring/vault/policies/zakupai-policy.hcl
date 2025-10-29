# Тонкая политика доступа: сервисы могут только читать и перечислять секреты внутри mount zakupai/
path "zakupai/*" {
  capabilities = ["read", "list"]
}
