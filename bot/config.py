"""
Конфигурация приложения с безопасным управлением переменными окружения
"""

import os
import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

# Загрузка переменных из .env файла
try:
    from dotenv import load_dotenv

    # Ищем .env в текущей директории (bot/.env)
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env from: {env_path}")
    else:
        print(f"⚠️ .env not found at: {env_path}")
except ImportError:
    print("⚠️ python-dotenv not installed, using system environment variables only")


class DatabaseConfig(BaseModel):
    """Конфигурация базы данных"""

    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    user: str = Field(min_length=1)
    password: str = Field(min_length=1)
    database: str = Field(min_length=1)

    @property
    def url(self) -> str:
        """Получение URL для подключения к БД"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def asyncpg_dsn(self) -> str:
        """DSN для asyncpg"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class TelegramConfig(BaseModel):
    """Конфигурация Telegram бота"""

    bot_token: str = Field(min_length=10)
    webhook_url: str | None = None
    webhook_secret: str | None = None

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v):
        """Валидация формата Telegram токена"""
        if not re.match(r"^\d+:[A-Za-z0-9_-]{35}$", v):
            raise ValueError("Invalid Telegram bot token format")
        return v


class APIConfig(BaseModel):
    """Конфигурация внешних API"""

    zakupai_base_url: str = Field(default="http://localhost:8080")
    zakupai_api_key: str = Field(default="", min_length=0)
    billing_service_url: str = Field(default="http://billing-service:7004")
    n8n_webhook_url: str = Field(default="")

    @field_validator("zakupai_base_url", "billing_service_url")
    @classmethod
    def validate_urls(cls, v):
        """Валидация URL"""
        if not re.match(r"^https?://.+", v):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("n8n_webhook_url")
    @classmethod
    def validate_n8n_webhook_url(cls, v):
        """Валидация n8n webhook URL"""
        if v and not re.match(r"^https?://.+", v):
            raise ValueError("n8n webhook URL must start with http:// or https://")
        return v


class SecurityConfig(BaseModel):
    """Конфигурация безопасности"""

    environment: str = Field(default="development")
    ssl_verify: bool = Field(default=True)
    request_timeout: int = Field(default=30, ge=1, le=300)
    max_requests_per_minute: int = Field(default=10, ge=1, le=1000)
    api_key_min_length: int = Field(default=10, ge=8, le=255)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Валидация окружения"""
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be: development, staging, or production")
        return v


class AppConfig(BaseModel):
    """Главная конфигурация приложения"""

    database: DatabaseConfig
    telegram: TelegramConfig
    api: APIConfig
    security: SecurityConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Создание конфигурации из переменных окружения"""

        # Проверяем обязательные переменные
        required_vars = [
            "TELEGRAM_BOT_TOKEN",
            "POSTGRES_HOST",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
        ]

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        return cls(
            database=DatabaseConfig(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                database=os.getenv("POSTGRES_DB"),
            ),
            telegram=TelegramConfig(
                bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
                webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL"),
                webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET"),
            ),
            api=APIConfig(
                zakupai_base_url=os.getenv("ZAKUPAI_API_URL", "http://localhost:8080"),
                zakupai_api_key=os.getenv("ZAKUPAI_API_KEY", ""),
                billing_service_url=os.getenv(
                    "BILLING_SERVICE_URL", "http://billing-service:7004"
                ),
                n8n_webhook_url=os.getenv("N8N_WEBHOOK_URL", ""),
            ),
            security=SecurityConfig(
                environment=os.getenv("ENVIRONMENT", "development"),
                ssl_verify=os.getenv("SSL_VERIFY", "true").lower() == "true",
                request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
                max_requests_per_minute=int(os.getenv("MAX_REQUESTS_PER_MINUTE", "10")),
                api_key_min_length=int(os.getenv("API_KEY_MIN_LENGTH", "10")),
            ),
        )


def mask_sensitive_data(data: str, show_last: int = 4) -> str:
    """Маскировка чувствительных данных для логирования"""
    if not data or len(data) <= show_last:
        return "*" * len(data) if data else ""
    return "*" * (len(data) - show_last) + data[-show_last:]


def validate_api_key_format(api_key: str) -> bool:
    """Валидация формата API ключа"""
    if not api_key or not isinstance(api_key, str):
        return False

    # UUID формат или другой безопасный формат
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    secure_pattern = r"^[A-Za-z0-9_-]{10,255}$"

    return bool(re.match(uuid_pattern, api_key) or re.match(secure_pattern, api_key))


# Глобальная конфигурация
config = AppConfig.from_env()
