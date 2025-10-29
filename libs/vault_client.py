"""Утилита для безопасной работы с HashiCorp Vault через hvac.

Использование:
    from libs.vault_client import VaultClient
    secrets = VaultClient().read("app")
    os.environ.update(secrets)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hvac

log = logging.getLogger("zakupai.vault")


class VaultClientError(RuntimeError):
    """Исключение, поднимаемое при любых проблемах доступа к Vault."""


def _bool_env(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes"}


def _resolve_verify() -> bool | str:
    # Позволяем отключать проверку сертификата в dev-режиме: VAULT_SKIP_VERIFY=true
    if _bool_env("VAULT_SKIP_VERIFY"):
        return False
    cert_path = os.getenv("VAULT_CACERT")
    if cert_path:
        path = Path(cert_path)
        if not path.exists():
            raise VaultClientError(f"Файл CA {cert_path} не найден")
        return str(path)
    return True


def _read_file(path: str | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        raise VaultClientError(f"Файл с кредами {path} не найден")
    return file_path.read_text(encoding="utf-8").strip()


@dataclass(slots=True)
class VaultSettings:
    """Набор параметров, отложенно читаемых из окружения."""

    address: str = os.getenv("VAULT_ADDR", "http://zakupai-vault:8200")
    mount_point: str = os.getenv("VAULT_KV_MOUNT", "zakupai")
    namespace: str | None = os.getenv("VAULT_NAMESPACE")
    role_id_file: str | None = os.getenv("VAULT_ROLE_ID_FILE")
    secret_id_file: str | None = os.getenv("VAULT_SECRET_ID_FILE")
    token_env: str | None = os.getenv("VAULT_TOKEN")
    token_file: str | None = os.getenv("VAULT_TOKEN_FILE")


class VaultClient:
    """Минималистичный клиент Vault с поддержкой AppRole и fallback на stateless токен."""

    def __init__(self, *, settings: VaultSettings | None = None) -> None:
        self.settings = settings or VaultSettings()
        verify = _resolve_verify()
        self._cache: dict[str, dict[str, Any]] = {}
        try:
            self._client = hvac.Client(
                url=self.settings.address,
                namespace=self.settings.namespace,
                verify=verify,
            )
        except Exception as exc:  # pragma: no cover - сетевые ошибки
            raise VaultClientError(f"Не удалось создать hvac.Client: {exc}") from exc
        self._authenticate()

    @property
    def client(self) -> hvac.Client:
        return self._client

    def _authenticate(self) -> None:
        """Пробуем AppRole→Token и подтверждаем аутентификацию."""
        # 1. AppRole (production способ)
        role_id = _read_file(self.settings.role_id_file)
        secret_id = _read_file(self.settings.secret_id_file)
        if role_id and secret_id:
            try:
                self._client.auth.approle.login(role_id=role_id, secret_id=secret_id)
            except hvac.exceptions.InvalidRequest as exc:
                raise VaultClientError(f"AppRole отклонён: {exc}") from exc
            except Exception as exc:
                raise VaultClientError(f"AppRole авторизация не удалась: {exc}") from exc
            if not self._client.is_authenticated():
                raise VaultClientError("AppRole авторизация не активировала сессию Vault")
            log.debug("Проверка Vault AppRole прошла успешно")
            return

        # 2. Fallback — токен для локальной разработки
        token = (self.settings.token_env or _read_file(self.settings.token_file) or "").strip()
        if token:
            self._client.token = token
            if not self._client.is_authenticated():
                raise VaultClientError("Переданный VAULT_TOKEN недействителен или просрочен")
            log.debug("Используем локальный VAULT_TOKEN для доступа к Vault")
            return

        raise VaultClientError(
            "Не заданы AppRole креды (VAULT_ROLE_ID_FILE/VAULT_SECRET_ID_FILE) "
            "и отсутствует fallback VAULT_TOKEN. Проверьте docker-compose.override.stage7.yml."
        )

    def read(self, name: str) -> dict[str, Any]:
        """Читает KV-секрет внутри mount zakupai и возвращает dict значений."""
        if name in self._cache:
            return dict(self._cache[name])
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=name, mount_point=self.settings.mount_point
            )
        except hvac.exceptions.InvalidPath as exc:
            raise VaultClientError(f"Секрет zakupai/{name} не найден") from exc
        except Exception as exc:  # pragma: no cover - сетевые ошибки
            raise VaultClientError(f"Ошибка чтения секрета zakupai/{name}: {exc}") from exc
        data = response.get("data", {}).get("data", {})
        if not isinstance(data, dict):
            raise VaultClientError(f"Некорректный формат данных у секрета zakupai/{name}")
        normalized = {k: str(v) for k, v in data.items()}
        self._cache[name] = normalized
        return dict(normalized)


__all__ = ["VaultClient", "VaultClientError", "VaultSettings"]
