"""Shared Vault helper utilities for ZakupAI services."""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import hvac

_DEFAULT_MOUNT = os.getenv("VAULT_KV_MOUNT", "zakupai")


class VaultClientError(RuntimeError):
    """Raised when Vault configuration is missing or incorrect."""


def _read_token() -> str:
    token = os.getenv("VAULT_TOKEN")
    if token:
        return token.strip()

    token_file = os.getenv("VAULT_TOKEN_FILE")
    if token_file:
        path = Path(token_file)
        if path.exists():
            return path.read_text().strip()

    raise VaultClientError(
        "Vault token not found. Set VAULT_TOKEN or VAULT_TOKEN_FILE before starting the service."
    )


def _should_verify_tls() -> str | bool:
    cert_path = os.getenv("VAULT_CACERT")
    if not cert_path:
        # Default to certificate verification. hvac will fall back to certifi bundle.
        return True

    lowered = cert_path.lower()
    if lowered in {"0", "false", "no"}:
        return False

    path = Path(cert_path)
    if not path.exists():
        raise VaultClientError(f"VAULT_CACERT points to missing file: {cert_path}")
    return str(path)


@lru_cache(maxsize=1)
def get_client() -> hvac.Client:
    url = os.getenv("VAULT_ADDR", "https://vault:8200")
    client = hvac.Client(url=url, token=_read_token(), verify=_should_verify_tls())
    if not client.is_authenticated():
        raise VaultClientError(
            "Authentication against Vault failed. Check token and policies."
        )
    return client


def read_kv(path: str, *, mount_point: str | None = None) -> dict:
    """Read a KV v2 secret and return its data payload."""
    client = get_client()
    mount = mount_point or _DEFAULT_MOUNT
    response = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount)
    return response["data"]["data"]


def load_kv_to_env(
    path: str,
    *,
    mapping: Mapping[str, str] | None = None,
    override: bool = False,
    mount_point: str | None = None,
) -> dict:
    """Load KV secrets and inject them into os.environ.

    Args:
        path: Secret path relative to the KV mount (e.g. "db").
        mapping: Optional mapping from secret keys to environment variable names.
        override: Overwrite existing environment variables when True.
        mount_point: Custom KV mount point; defaults to VAULT_KV_MOUNT or "zakupai".
    Returns:
        The raw secret dictionary fetched from Vault.
    """

    data = read_kv(path, mount_point=mount_point)
    if mapping:
        items = {env_key: data[key] for key, env_key in mapping.items() if key in data}
    else:
        items = data

    for env_key, value in items.items():
        if override or not os.environ.get(env_key):
            os.environ[env_key] = str(value)

    return data


__all__ = ["VaultClientError", "get_client", "read_kv", "load_kv_to_env"]
