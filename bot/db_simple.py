import asyncio
import logging
from contextlib import asynccontextmanager

import asyncpg
from config import config

logger = logging.getLogger(__name__)

# Глобальный connection pool
_connection_pool: asyncpg.Pool | None = None


async def init_db_pool() -> asyncpg.Pool:
    """Инициализация connection pool для базы данных"""
    global _connection_pool

    if _connection_pool is not None:
        return _connection_pool

    max_retries = 3
    for attempt in range(max_retries):
        try:
            _connection_pool = await asyncpg.create_pool(
                host=config.database.host,
                port=config.database.port,
                user=config.database.user,
                password=config.database.password,
                database=config.database.database,
                min_size=2,
                max_size=10,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                command_timeout=10,
                server_settings={
                    "application_name": "zakupai-telegram-bot",
                    "timezone": "UTC",
                },
            )
            logger.info("Database connection pool initialized successfully")
            return _connection_pool

        except Exception as e:
            logger.error(
                f"Failed to create DB pool (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2**attempt)  # Exponential backoff


async def close_db_pool():
    """Закрытие connection pool"""
    global _connection_pool
    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None
        logger.info("Database connection pool closed")


@asynccontextmanager
async def get_db_connection():
    """Контекстный менеджер для получения соединения из pool"""
    if _connection_pool is None:
        await init_db_pool()

    async with _connection_pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            logger.error(f"Database operation failed: {type(e).__name__}")
            raise


async def get_api_key(user_id: int) -> str | None:
    """Получение API ключа пользователя с валидацией входных данных"""
    # Валидация входных данных
    if not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"Invalid user_id for get_api_key: {user_id}")
        return None

    try:
        async with get_db_connection() as conn:
            result = await conn.fetchval(
                "SELECT api_key FROM tg_keys WHERE chat_id = $1 AND api_key IS NOT NULL",
                user_id,
            )
            return result
    except Exception as e:
        logger.error(f"Failed to get API key for user {user_id}: {type(e).__name__}")
        return None


async def save_api_key(user_id: int, api_key: str) -> bool:
    """Сохранение API ключа пользователя с валидацией входных данных"""
    # Валидация входных данных
    if not isinstance(user_id, int) or user_id <= 0:
        logger.error(f"Invalid user_id for save_api_key: {user_id}")
        return False

    if (
        not isinstance(api_key, str)
        or len(api_key) < config.security.api_key_min_length
        or len(api_key) > 255
    ):
        logger.error(f"Invalid API key format for user {user_id}")
        return False

    try:
        async with get_db_connection() as conn:
            await conn.execute(
                """INSERT INTO tg_keys (chat_id, api_key, updated_at)
                   VALUES ($1, $2, now())
                   ON CONFLICT (chat_id) DO UPDATE SET
                   api_key = $2, updated_at = now()""",
                user_id,
                api_key,
            )
            logger.debug(f"API key saved for user {user_id}")
            return True
    except Exception as e:
        logger.error(f"Failed to save API key for user {user_id}: {type(e).__name__}")
        return False


async def init_db():
    """Инициализация схемы базы данных"""
    try:
        # Сначала инициализируем pool
        await init_db_pool()

        async with get_db_connection() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tg_keys (
                    chat_id BIGINT PRIMARY KEY,
                    api_key TEXT NOT NULL CHECK (length(api_key) >= 10 AND length(api_key) <= 255),
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )

            # Создаем индекс для быстрого поиска по api_key (если нужен)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tg_keys_api_key ON tg_keys(api_key)"
            )

            logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {type(e).__name__}")
        raise


async def health_check() -> bool:
    """Проверка состояния базы данных"""
    try:
        async with get_db_connection() as conn:
            await conn.fetchval("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {type(e).__name__}")
        return False
