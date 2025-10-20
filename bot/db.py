import asyncio
import logging
import os
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Глобальный пул соединений
_connection_pool: Pool | None = None


class DatabaseError(Exception):
    """Кастомное исключение для ошибок БД"""

    pass


async def get_connection_pool() -> Pool:
    """
    Получение пула соединений с БД
    """
    global _connection_pool

    if _connection_pool is None:
        database_url = os.getenv(
            "DATABASE_URL", "postgresql://zakupai:password123@localhost:5432/zakupai"
        )

        try:
            _connection_pool = await asyncpg.create_pool(
                database_url, min_size=1, max_size=10, command_timeout=30
            )
            logger.info("Connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise DatabaseError(f"Database connection failed: {e}") from e

    return _connection_pool


async def close_connection_pool():
    """
    Закрытие пула соединений
    """
    global _connection_pool

    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None
        logger.info("Connection pool closed")


@asynccontextmanager
async def get_connection():
    """
    Контекстный менеджер для получения соединения из пула
    """
    pool = await get_connection_pool()
    async with pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise DatabaseError(f"Database operation failed: {e}") from e


async def init_db():
    """
    Инициализация таблиц БД
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS tg_keys (
        user_id BIGINT PRIMARY KEY,
        api_key TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE
    );

    CREATE INDEX IF NOT EXISTS idx_tg_keys_user_id ON tg_keys(user_id);
    CREATE INDEX IF NOT EXISTS idx_tg_keys_created_at ON tg_keys(created_at DESC);
    """

    try:
        async with get_connection() as conn:
            await conn.execute(create_table_sql)
            logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise DatabaseError(f"Database initialization failed: {e}") from e


async def save_api_key(user_id: int, api_key: str) -> bool:
    """
    Сохранение API ключа для пользователя

    Args:
        user_id: Telegram user ID
        api_key: API ключ для ZakupAI

    Returns:
        bool: True если успешно сохранён
    """
    upsert_sql = """
    INSERT INTO tg_keys (user_id, api_key, updated_at)
    VALUES ($1, $2, CURRENT_TIMESTAMP)
    ON CONFLICT (user_id)
    DO UPDATE SET
        api_key = EXCLUDED.api_key,
        updated_at = CURRENT_TIMESTAMP,
        is_active = TRUE
    """

    try:
        async with get_connection() as conn:
            await conn.execute(upsert_sql, user_id, api_key)
            logger.info(f"API key saved for user {user_id}")
            return True
    except Exception as e:
        logger.error(f"Failed to save API key for user {user_id}: {e}")
        return False


async def get_api_key(user_id: int) -> str | None:
    """
    Получение API ключа пользователя

    Args:
        user_id: Telegram user ID

    Returns:
        Optional[str]: API ключ или None если не найден
    """
    select_sql = """
    SELECT api_key
    FROM tg_keys
    WHERE user_id = $1 AND is_active = TRUE
    """

    try:
        async with get_connection() as conn:
            result = await conn.fetchval(select_sql, user_id)
            return result
    except Exception as e:
        logger.error(f"Failed to get API key for user {user_id}: {e}")
        return None


async def deactivate_api_key(user_id: int) -> bool:
    """
    Деактивация API ключа пользователя

    Args:
        user_id: Telegram user ID

    Returns:
        bool: True если успешно деактивирован
    """
    deactivate_sql = """
    UPDATE tg_keys
    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
    WHERE user_id = $1
    """

    try:
        async with get_connection() as conn:
            result = await conn.execute(deactivate_sql, user_id)
            affected_rows = int(result.split()[-1])

            if affected_rows > 0:
                logger.info(f"API key deactivated for user {user_id}")
                return True
            else:
                logger.warning(f"No API key found to deactivate for user {user_id}")
                return False
    except Exception as e:
        logger.error(f"Failed to deactivate API key for user {user_id}: {e}")
        return False


async def get_user_stats(user_id: int) -> dict | None:
    """
    Получение статистики пользователя

    Args:
        user_id: Telegram user ID

    Returns:
        Optional[dict]: Статистика или None
    """
    stats_sql = """
    SELECT
        user_id,
        created_at,
        updated_at,
        is_active
    FROM tg_keys
    WHERE user_id = $1
    """

    try:
        async with get_connection() as conn:
            result = await conn.fetchrow(stats_sql, user_id)

            if result:
                return {
                    "user_id": result["user_id"],
                    "registered_at": result["created_at"],
                    "last_updated": result["updated_at"],
                    "is_active": result["is_active"],
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get stats for user {user_id}: {e}")
        return None


async def get_active_users_count() -> int:
    """
    Получение количества активных пользователей

    Returns:
        int: Количество активных пользователей
    """
    count_sql = "SELECT COUNT(*) FROM tg_keys WHERE is_active = TRUE"

    try:
        async with get_connection() as conn:
            result = await conn.fetchval(count_sql)
            return result or 0
    except Exception as e:
        logger.error(f"Failed to get active users count: {e}")
        return 0


async def cleanup_old_keys(days_old: int = 90) -> int:
    """
    Очистка старых неактивных ключей

    Args:
        days_old: Количество дней для считывания ключа устаревшим

    Returns:
        int: Количество удалённых записей
    """
    cleanup_sql = """
    DELETE FROM tg_keys
    WHERE is_active = FALSE
    AND updated_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
    """

    try:
        async with get_connection() as conn:
            result = await conn.execute(cleanup_sql % days_old)
            deleted_count = int(result.split()[-1])
            logger.info(f"Cleaned up {deleted_count} old API keys")
            return deleted_count
    except Exception as e:
        logger.error(f"Failed to cleanup old keys: {e}")
        return 0


async def health_check() -> bool:
    """
    Проверка здоровья подключения к БД

    Returns:
        bool: True если БД доступна
    """
    try:
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# Утилиты для тестирования
async def reset_test_data():
    """
    Очистка тестовых данных (только для тестов!)
    """
    if os.getenv("ENVIRONMENT") != "test":
        raise RuntimeError("reset_test_data can only be used in test environment")

    try:
        async with get_connection() as conn:
            await conn.execute("DELETE FROM tg_keys WHERE user_id < 1000000")
            logger.info("Test data cleared")
    except Exception as e:
        logger.error(f"Failed to reset test data: {e}")
        raise DatabaseError(f"Test data reset failed: {e}") from e


if __name__ == "__main__":
    # Простой тест подключения
    async def test_connection():
        try:
            await init_db()
            is_healthy = await health_check()
            print(f"Database health: {'OK' if is_healthy else 'FAILED'}")

            # Тестовые операции
            test_user_id = 123456789
            test_api_key = "test-key-12345"

            # Сохранение
            saved = await save_api_key(test_user_id, test_api_key)
            print(f"Save API key: {'OK' if saved else 'FAILED'}")

            # Получение
            retrieved_key = await get_api_key(test_user_id)
            print(f"Get API key: {'OK' if retrieved_key == test_api_key else 'FAILED'}")

            # Статистика
            stats = await get_user_stats(test_user_id)
            print(f"Get stats: {'OK' if stats else 'FAILED'}")

            # Деактивация
            deactivated = await deactivate_api_key(test_user_id)
            print(f"Deactivate key: {'OK' if deactivated else 'FAILED'}")

            await close_connection_pool()

        except Exception as e:
            print(f"Test failed: {e}")

    asyncio.run(test_connection())
