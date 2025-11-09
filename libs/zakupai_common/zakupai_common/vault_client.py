"""
Vault HVAC client with AppRole authentication and fallback support.
"""
import os
import logging
from typing import Dict, Optional, Any
from functools import lru_cache

try:
    import hvac
    HVAC_AVAILABLE = True
except ImportError:
    HVAC_AVAILABLE = False
    logging.warning("hvac package not installed - Vault integration disabled")

logger = logging.getLogger(__name__)


class VaultClient:
    """Production-ready Vault client with AppRole auth and env fallback."""

    def __init__(self, enable_fallback: bool = True):
        self.vault_addr = os.getenv("VAULT_ADDR", "http://vault:8200")
        self.enable_fallback = enable_fallback
        self._client: Optional[Any] = None
        self._authenticated = False

        # Support both file-based and direct env var credentials
        self.role_id = self._get_credential("VAULT_ROLE_ID")
        self.secret_id = self._get_credential("VAULT_SECRET_ID")

    def _get_credential(self, env_var: str) -> Optional[str]:
        """Get credential from env var or file."""
        # Try direct env var first
        value = os.getenv(env_var)
        if value:
            return value

        # Try file-based credential
        file_var = f"{env_var}_FILE"
        file_path = os.getenv(file_var)
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")

        return None

    def authenticate(self) -> bool:
        """Authenticate with Vault using AppRole."""
        if not HVAC_AVAILABLE:
            logger.warning("hvac not available - using fallback mode")
            return False

        if not self.role_id or not self.secret_id:
            logger.warning("Missing VAULT_ROLE_ID or VAULT_SECRET_ID - using fallback")
            return False

        try:
            self._client = hvac.Client(url=self.vault_addr)

            # Check Vault health
            if not self._client.sys.is_initialized():
                raise Exception("Vault is not initialized")

            if self._client.sys.is_sealed():
                raise Exception("Vault is sealed")

            # Authenticate with AppRole
            auth_response = self._client.auth.approle.login(
                role_id=self.role_id,
                secret_id=self.secret_id
            )

            self._authenticated = self._client.is_authenticated()

            if self._authenticated:
                logger.info(f"✅ Vault authentication successful (addr: {self.vault_addr})")
                return True
            else:
                raise Exception("Authentication failed - invalid token")

        except Exception as e:
            logger.error(f"❌ Vault authentication failed: {e}")
            self._authenticated = False
            return False

    @lru_cache(maxsize=128)
    def get_secret(self, path: str, key: Optional[str] = None) -> Any:
        """
        Get secret from Vault with fallback to environment variables.

        Args:
            path: Vault KV path (e.g., "shared/db" or "services/etl/openai")
            key: Specific key to extract (optional)

        Returns:
            Secret value or dict of all secrets at path
        """
        # Try Vault first
        if not self._authenticated:
            self.authenticate()

        if self._authenticated and self._client:
            try:
                # Construct full path with mount point
                full_path = path if path.startswith("zakupai/") else f"zakupai/{path}"

                result = self._client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point="zakupai"
                )
                data = result["data"]["data"]

                logger.info(f"✅ Loaded secret from Vault: {path}")

                if key:
                    return data.get(key)
                return data

            except Exception as e:
                logger.warning(f"⚠️ Failed to read {path} from Vault: {e}")

        # Fallback to environment variables
        if self.enable_fallback:
            logger.warning(f"⚠️ Using environment fallback for {path}")
            return self._get_env_fallback(path, key)

        raise Exception(f"Cannot load secret {path} and fallback is disabled")

    def _get_env_fallback(self, path: str, key: Optional[str] = None) -> Any:
        """Fallback to environment variables for development."""
        # Map Vault paths to env variables
        env_mapping = {
            "shared/db": {
                "POSTGRES_USER": os.getenv("POSTGRES_USER"),
                "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
                "DATABASE_URL": os.getenv("DATABASE_URL")
            },
            "shared/redis": {
                "REDIS_URL": os.getenv("REDIS_URL", "redis://redis:6379"),
                "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD", "")
            },
            "shared/jwt": {
                "JWT_SECRET": os.getenv("JWT_SECRET")
            },
            "services/etl/openai": {
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")
            },
            "services/etl/telegram": {
                "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN"),
                "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN")
            },
            "backup/b2": {
                "B2_KEY_ID": os.getenv("B2_KEY_ID"),
                "B2_APP_KEY": os.getenv("B2_APP_KEY"),
                "BACKBLAZE_KEY_ID": os.getenv("BACKBLAZE_KEY_ID"),
                "BACKBLAZE_APPLICATION_KEY": os.getenv("BACKBLAZE_APPLICATION_KEY")
            }
        }

        data = env_mapping.get(path, {})

        if key:
            return data.get(key)
        return data

    def health_check(self) -> Dict[str, Any]:
        """Check Vault connectivity and authentication status."""
        return {
            "vault_address": self.vault_addr,
            "authenticated": self._authenticated,
            "fallback_enabled": self.enable_fallback
        }


# Global singleton instance
_vault_client: Optional[VaultClient] = None


def get_vault_client(enable_fallback: bool = True) -> VaultClient:
    """Get or create global Vault client instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient(enable_fallback=enable_fallback)
    return _vault_client
