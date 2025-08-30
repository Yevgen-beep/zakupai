import os
from unittest.mock import AsyncMock, patch

import pytest

from bot.db import (
    DatabaseError,
    deactivate_api_key,
    get_active_users_count,
    get_api_key,
    get_user_stats,
    health_check,
    init_db,
    save_api_key,
)


class TestDatabaseOperations:
    """Тесты операций с базой данных"""

    @pytest.mark.asyncio
    async def test_save_and_get_api_key_success(self):
        """Тест успешного сохранения и получения API ключа"""
        user_id = 123456789
        api_key = "test-api-key-12345"

        # Mock соединения с БД
        mock_conn = AsyncMock()

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            # Тест сохранения
            result = await save_api_key(user_id, api_key)
            assert result is True

            # Проверяем вызов execute
            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            assert user_id in call_args[0]
            assert api_key in call_args[0]

    @pytest.mark.asyncio
    async def test_get_api_key_success(self):
        """Тест успешного получения API ключа"""
        user_id = 123456789
        expected_key = "test-api-key-12345"

        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = expected_key

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_api_key(user_id)

            assert result == expected_key
            mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_api_key_not_found(self):
        """Тест получения несуществующего API ключа"""
        user_id = 999999999

        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = None

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_api_key(user_id)

            assert result is None

    @pytest.mark.asyncio
    async def test_deactivate_api_key_success(self):
        """Тест успешной деактивации API ключа"""
        user_id = 123456789

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "UPDATE 1"  # Одна запись обновлена

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await deactivate_api_key(user_id)

            assert result is True
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_api_key_not_found(self):
        """Тест деактивации несуществующего API ключа"""
        user_id = 999999999

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "UPDATE 0"  # Ни одной записи не обновлено

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await deactivate_api_key(user_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_user_stats_success(self):
        """Тест получения статистики пользователя"""
        user_id = 123456789
        expected_stats = {
            "user_id": user_id,
            "registered_at": "2024-01-01 10:00:00",
            "last_updated": "2024-01-02 10:00:00",
            "is_active": True,
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = expected_stats

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_user_stats(user_id)

            assert result == expected_stats
            mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_users_count(self):
        """Тест получения количества активных пользователей"""
        expected_count = 42

        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = expected_count

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_active_users_count()

            assert result == expected_count
            mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Тест успешной проверки здоровья БД"""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 1

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await health_check()

            assert result is True
            mock_conn.fetchval.assert_called_with("SELECT 1")

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Тест неудачной проверки здоровья БД"""
        with patch("bot.db.get_connection", side_effect=Exception("Connection failed")):
            result = await health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_init_db_success(self):
        """Тест успешной инициализации БД"""
        mock_conn = AsyncMock()

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            await init_db()

            # Проверяем, что SQL для создания таблиц был выполнен
            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            assert "CREATE TABLE IF NOT EXISTS tg_keys" in call_args

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Тест обработки ошибок базы данных"""
        user_id = 123456789

        with patch("bot.db.get_connection", side_effect=Exception("Database error")):
            # Все операции должны возвращать False или None при ошибках
            assert await save_api_key(user_id, "test-key") is False
            assert await get_api_key(user_id) is None
            assert await deactivate_api_key(user_id) is False
            assert await get_user_stats(user_id) is None
            assert await get_active_users_count() == 0


class TestDatabaseConnection:
    """Тесты подключения к базе данных"""

    @pytest.mark.asyncio
    async def test_connection_pool_creation(self):
        """Тест создания пула соединений"""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            # Очищаем глобальный пул для теста
            import bot.db
            from bot.db import get_connection_pool

            bot.db._connection_pool = None

            pool = await get_connection_pool()

            assert pool == mock_pool
            mock_create_pool.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_pool_failure(self):
        """Тест неудачного создания пула соединений"""
        with patch("asyncpg.create_pool", side_effect=Exception("Connection failed")):
            # Очищаем глобальный пул для теста
            import bot.db
            from bot.db import get_connection_pool

            bot.db._connection_pool = None

            with pytest.raises(DatabaseError, match="Database connection failed"):
                await get_connection_pool()


class TestDatabaseUtilities:
    """Тесты вспомогательных функций БД"""

    @pytest.mark.asyncio
    async def test_cleanup_old_keys(self):
        """Тест очистки старых ключей"""
        from bot.db import cleanup_old_keys

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "DELETE 5"  # 5 записей удалено

        with patch("bot.db.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await cleanup_old_keys(90)

            assert result == 5
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_test_data_not_in_test_env(self):
        """Тест что reset_test_data не работает не в тестовом окружении"""
        from bot.db import reset_test_data

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(
                RuntimeError, match="can only be used in test environment"
            ):
                await reset_test_data()

    @pytest.mark.asyncio
    async def test_reset_test_data_in_test_env(self):
        """Тест reset_test_data в тестовом окружении"""
        from bot.db import reset_test_data

        mock_conn = AsyncMock()

        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            with patch("bot.db.get_connection") as mock_get_conn:
                mock_get_conn.return_value.__aenter__.return_value = mock_conn

                await reset_test_data()

                mock_conn.execute.assert_called_once()
                call_args = mock_conn.execute.call_args[0][0]
                assert "DELETE FROM tg_keys" in call_args


@pytest.fixture
def mock_db_env():
    """Фикстура для mock переменных окружения БД"""
    test_env = {"DATABASE_URL": "postgresql://test:test@localhost:5432/test_zakupai"}

    with patch.dict(os.environ, test_env):
        yield test_env


@pytest.mark.asyncio
async def test_database_url_from_env(mock_db_env):
    """Тест получения URL БД из переменных окружения"""
    from bot.db import get_connection_pool

    with patch("asyncpg.create_pool") as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        # Очищаем глобальный пул
        import bot.db

        bot.db._connection_pool = None

        await get_connection_pool()

        # Проверяем, что был использован правильный URL
        call_args = mock_create_pool.call_args[0]
        assert mock_db_env["DATABASE_URL"] in call_args
