import os

import hvac

client = hvac.Client(url=os.getenv("VAULT_ADDR", "http://vault:8200"))
client.token = os.getenv("VAULT_TOKEN")


def get_secret(path: str, key: str):
    try:
        data = client.secrets.kv.v2.read_secret_version(path=path)
    except Exception as exc:  # pragma: no cover - network dependent
        raise RuntimeError(f"Vault read error: {exc}") from exc
    return data["data"]["data"].get(key)
